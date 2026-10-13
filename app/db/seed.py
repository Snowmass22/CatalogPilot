"""Database seed script populating 10 realistic sample products, categories, and attributes."""

from typing import Any

from sqlmodel import Session, select

from app.db.models import AttributeDef, Category, Product
from app.db.session import engine, init_db
from app.domain.schemas import (
    AttributeDefCreate,
    CategoryCreate,
    ProductAttributeInput,
    ProductCreate,
)
from app.services.attribute_service import AttributeService
from app.services.category_service import CategoryService
from app.services.product_service import ProductService


def seed_database(session: Session) -> dict[str, int]:
    """Seed categories, attributes, and 10 sample products idempotently."""
    init_db()

    # 1. Categories
    category_map: dict[str, Category] = {}
    categories_data: list[dict[str, Any]] = [
        {"name": "Apparel", "parent_id": None},
        {"name": "Accessories", "parent_id": None},
    ]

    for item in categories_data:
        name_str = str(item["name"])
        existing = session.exec(select(Category).where(Category.name == name_str)).first()
        if not existing:
            cat = CategoryService.create(
                session, CategoryCreate(name=name_str, parent_id=item["parent_id"])
            )
            category_map[name_str] = cat
        else:
            category_map[name_str] = existing

    # Child categories under Apparel
    apparel_cat = category_map["Apparel"]
    apparel_id = apparel_cat.id
    child_categories: list[dict[str, Any]] = [
        {"name": "Hoodies", "parent_id": apparel_id},
        {"name": "T-Shirts", "parent_id": apparel_id},
    ]
    for item in child_categories:
        name_str = str(item["name"])
        existing = session.exec(select(Category).where(Category.name == name_str)).first()
        if not existing:
            cat = CategoryService.create(
                session, CategoryCreate(name=name_str, parent_id=item["parent_id"])
            )
            category_map[name_str] = cat
        else:
            category_map[name_str] = existing

    # 2. Attribute Definitions
    attr_defs_data: list[dict[str, Any]] = [
        {
            "name": "Color",
            "type": "select",
            "allowed_values": ["Black", "White", "Navy", "Heather Grey", "Olive", "Burgundy"],
        },
        {
            "name": "Size",
            "type": "select",
            "allowed_values": ["XS", "S", "M", "L", "XL", "XXL"],
        },
        {
            "name": "Material",
            "type": "text",
            "allowed_values": None,
        },
    ]

    attr_map: dict[str, AttributeDef] = {}
    for item in attr_defs_data:
        name_str = str(item["name"])
        existing_attr = session.exec(
            select(AttributeDef).where(AttributeDef.name == name_str)
        ).first()
        if not existing_attr:
            attr = AttributeService.create(
                session,
                AttributeDefCreate(
                    name=name_str,
                    type=item["type"],
                    allowed_values=item["allowed_values"],
                ),
            )
            attr_map[name_str] = attr
        else:
            attr_map[name_str] = existing_attr

    # 3. 10 Sample Products
    sample_products: list[dict[str, Any]] = [
        {
            "sku": "HOOD-001-BLK",
            "name": "Classic Heavyweight Hoodie",
            "description": "Ultra-soft 450 GSM fleece hoodie with ribbed cuffs and kangaroo pocket.",
            "price": 64.99,
            "stock": 45,
            "category": "Hoodies",
            "status": "active",
            "health_score": 95,
            "attributes": [
                {"name": "Color", "value": "Black"},
                {"name": "Size", "value": "L"},
                {"name": "Material", "value": "Cotton Fleece"},
            ],
        },
        {
            "sku": "HOOD-002-GRY",
            "name": "Vintage Zip-Up Hoodie",
            "description": "Pre-washed vintage style zip hoodie with antique brass zipper.",
            "price": 69.50,
            "stock": 30,
            "category": "Hoodies",
            "status": "active",
            "health_score": 90,
            "attributes": [
                {"name": "Color", "value": "Heather Grey"},
                {"name": "Size", "value": "M"},
                {"name": "Material", "value": "Cotton Blend"},
            ],
        },
        {
            "sku": "TEE-001-WHT",
            "name": "Organic Cotton Crewneck Tee",
            "description": "Everyday breathable tee made with 100% certified organic cotton.",
            "price": 28.00,
            "stock": 120,
            "category": "T-Shirts",
            "status": "active",
            "health_score": 92,
            "attributes": [
                {"name": "Color", "value": "White"},
                {"name": "Size", "value": "M"},
                {"name": "Material", "value": "100% Organic Cotton"},
            ],
        },
        {
            "sku": "TEE-002-NAV",
            "name": "Heavyweight Boxy Fit Tee",
            "description": "Drop-shoulder streetwear cut with tight collar and relaxed drape.",
            "price": 34.00,
            "stock": 75,
            "category": "T-Shirts",
            "status": "active",
            "health_score": 88,
            "attributes": [
                {"name": "Color", "value": "Navy"},
                {"name": "Size", "value": "L"},
                {"name": "Material", "value": "Heavy Cotton"},
            ],
        },
        {
            "sku": "TEE-003-OLV",
            "name": "Acid Wash Pocket Tee",
            "description": "Mineral-washed cotton tee with chest pocket and distressed hems.",
            "price": 32.50,
            "stock": 50,
            "category": "T-Shirts",
            "status": "active",
            "health_score": 85,
            "attributes": [
                {"name": "Color", "value": "Olive"},
                {"name": "Size", "value": "XL"},
                {"name": "Material", "value": "Cotton"},
            ],
        },
        {
            "sku": "ACC-001-BLK",
            "name": "Waterproof Commuter Backpack",
            "description": "Roll-top 22L everyday backpack with padded laptop sleeve.",
            "price": 89.00,
            "stock": 25,
            "category": "Accessories",
            "status": "active",
            "health_score": 94,
            "attributes": [
                {"name": "Color", "value": "Black"},
                {"name": "Material", "value": "Cordura Nylon"},
            ],
        },
        {
            "sku": "ACC-002-NVY",
            "name": "Heavy Canvas Daily Tote",
            "description": "Reinforced heavy-duty 16oz canvas tote with inner zippered pouch.",
            "price": 24.00,
            "stock": 60,
            "category": "Accessories",
            "status": "active",
            "health_score": 80,
            "attributes": [
                {"name": "Color", "value": "Navy"},
                {"name": "Material", "value": "16oz Canvas"},
            ],
        },
        {
            "sku": "ACC-003-BLK",
            "name": "Ribbed Wool Knit Beanie",
            "description": "Warm merino wool blend beanie with fold-over cuff.",
            "price": 22.00,
            "stock": 80,
            "category": "Accessories",
            "status": "active",
            "health_score": 82,
            "attributes": [
                {"name": "Color", "value": "Black"},
                {"name": "Material", "value": "Merino Wool Blend"},
            ],
        },
        {
            "sku": "ACC-004-OLV",
            "name": "Waxed Cotton Snapback Cap",
            "description": "Weather-resistant waxed cotton 6-panel cap with brass buckle.",
            "price": 29.50,
            "stock": 40,
            "category": "Accessories",
            "status": "active",
            "health_score": 87,
            "attributes": [
                {"name": "Color", "value": "Olive"},
                {"name": "Material", "value": "Waxed Cotton"},
            ],
        },
        {
            "sku": "HOOD-003-BUR",
            "name": "Oversized Fleece Pullover",
            "description": "Relaxed drop-shoulder silhouette with brushed interior fleece.",
            "price": 58.00,
            "stock": 35,
            "category": "Hoodies",
            "status": "draft",
            "health_score": 75,
            "attributes": [
                {"name": "Color", "value": "Burgundy"},
                {"name": "Size", "value": "XL"},
                {"name": "Material", "value": "Brushed Fleece"},
            ],
        },
    ]

    products_created = 0
    for p_data in sample_products:
        sku_str = str(p_data["sku"])
        existing_prod = session.exec(select(Product).where(Product.sku == sku_str)).first()
        if existing_prod:
            continue

        matched_cat = category_map.get(str(p_data["category"]))
        category_id = matched_cat.id if matched_cat else None

        attr_inputs: list[ProductAttributeInput] = []
        raw_attrs: list[dict[str, str]] = p_data["attributes"]
        for a in raw_attrs:
            attr_def = attr_map.get(a["name"])
            if attr_def and attr_def.id:
                attr_inputs.append(
                    ProductAttributeInput(attribute_id=attr_def.id, value=a["value"])
                )

        create_schema = ProductCreate(
            sku=sku_str,
            name=str(p_data["name"]),
            description=str(p_data["description"]),
            price=float(p_data["price"]),
            stock=int(p_data["stock"]),
            category_id=category_id,
            status=str(p_data["status"]),
            health_score=int(p_data["health_score"]),
            attributes=attr_inputs,
        )
        ProductService.create(session, create_schema)
        products_created += 1

    return {
        "categories": len(category_map),
        "attributes": len(attr_map),
        "products_seeded": products_created,
    }


def main() -> None:
    """Entry point for standalone seed script execution."""
    print("Seeding database with sample catalog data...")
    with Session(engine) as session:
        result = seed_database(session)
    print(
        f"Seeding completed successfully! "
        f"Categories: {result['categories']}, "
        f"Attributes: {result['attributes']}, "
        f"Products seeded: {result['products_seeded']}"
    )


if __name__ == "__main__":
    main()
