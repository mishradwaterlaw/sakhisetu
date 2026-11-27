"""Pure deterministic order validation (§4.6). Zero LLM calls."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import Product, TaskTemplate, TemplateRequirement
from app.models.intake import Order
from app.models.people import Member
from app.models.planning import Inventory


@dataclass
class ValidationIssue:
    field: str
    code: str
    message: str


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)


def validate_order_deterministic(
    db: Session,
    *,
    shg_id: str,
    buyer_party_id: str | None,
    product_id: str | None,
    quantity: int | None,
    due_date: datetime | None,
    offered_price_per_unit_inr: float | None,
    exclude_order_id: str | None = None,
    now: datetime | None = None,
) -> ValidationResult:
    """Validate an extracted order deterministically without any model call."""
    issues: list[ValidationIssue] = []
    now = now or datetime.now(timezone.utc)

    # 1. Required fields
    if not buyer_party_id:
        issues.append(ValidationIssue("buyer", "MISSING_BUYER", "Buyer must be identified."))
    if not product_id:
        issues.append(ValidationIssue("product", "MISSING_PRODUCT", "Product must be specified."))
    if quantity is None or quantity <= 0:
        issues.append(ValidationIssue("quantity", "INVALID_QUANTITY", "Quantity must be a positive integer."))
    if due_date is None:
        issues.append(ValidationIssue("due_date", "MISSING_DUE_DATE", "Due date is required."))
    else:
        dd = due_date if due_date.tzinfo else due_date.replace(tzinfo=timezone.utc)
        if dd <= now:
            issues.append(ValidationIssue("due_date", "PAST_DUE_DATE", "Due date must be in the future."))
    if offered_price_per_unit_inr is None or offered_price_per_unit_inr <= 0:
        issues.append(
            ValidationIssue("offered_price", "INVALID_PRICE", "Offered price per unit must be positive.")
        )

    # 2. Product exists in catalogue
    product = None
    if product_id:
        product = db.scalar(select(Product).where(Product.id == product_id, Product.is_active.is_(True)))
        if not product:
            issues.append(
                ValidationIssue("product", "PRODUCT_NOT_IN_CATALOGUE", "Product does not exist in active catalogue.")
            )

    # 3. Duplicate-order check (same SHG + buyer + product + active status)
    if buyer_party_id and product_id and quantity and due_date:
        stmt = select(Order).where(
            Order.shg_id == shg_id,
            Order.buyer_party_id == buyer_party_id,
            Order.product_id == product_id,
            Order.quantity == quantity,
            Order.status.notin_(["CANCELLED", "DISBURSED"]),
        )
        if exclude_order_id:
            stmt = stmt.where(Order.id != exclude_order_id)
        dup = db.scalar(stmt)
        if dup:
            issues.append(
                ValidationIssue(
                    "order",
                    "DUPLICATE_ORDER",
                    f"Potential duplicate of existing active order {dup.order_code}.",
                )
            )

    # 4. Tool & material dependency feasibility
    if product and quantity and quantity > 0:
        templates = db.scalars(
            select(TaskTemplate).where(TaskTemplate.product_id == product.id)
        ).all()
        members = db.scalars(
            select(Member).where(Member.shg_id == shg_id, Member.is_active.is_(True))
        ).all()

        member_skills = {s for m in members for s in (m.skills or [])}
        member_tools = {t for m in members for t in (m.tools or [])}

        for tmpl in templates:
            if tmpl.required_skill not in member_skills:
                issues.append(
                    ValidationIssue(
                        "skills",
                        "MISSING_SKILL_IN_SHG",
                        f"No active member has required skill '{tmpl.required_skill}' for step '{tmpl.step_name}'.",
                    )
                )
            reqs = db.scalars(
                select(TemplateRequirement).where(TemplateRequirement.task_template_id == tmpl.id)
            ).all()
            for req in reqs:
                if req.requirement_type == "tool" and req.tool_id:
                    from app.models.catalogue import Tool

                    tool = db.get(Tool, req.tool_id)
                    if tool and tool.name not in member_tools:
                        issues.append(
                            ValidationIssue(
                                "tools",
                                "MISSING_TOOL_IN_SHG",
                                f"Required tool '{tool.name}' for step '{tmpl.step_name}' is not available.",
                            )
                        )
                elif req.requirement_type == "material" and req.material_id:
                    inv = db.scalar(
                        select(Inventory).where(
                            Inventory.shg_id == shg_id, Inventory.material_id == req.material_id
                        )
                    )
                    needed = req.quantity_per_unit * quantity
                    on_hand = inv.quantity_on_hand if inv else 0.0
                    if on_hand < needed:
                        issues.append(
                            ValidationIssue(
                                "materials",
                                "INSUFFICIENT_MATERIAL",
                                f"Material shortfall for step '{tmpl.step_name}': need {needed:.1f}, on hand {on_hand:.1f}.",
                            )
                        )

    return ValidationResult(is_valid=len(issues) == 0, issues=issues)
