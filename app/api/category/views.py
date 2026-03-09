from . import category
from flask import jsonify, request
from app import db
from app.models.category import Category as Category
from app.models.merchant import Merchant
from app.models.offer import Offer
from sqlalchemy.orm import joinedload, subqueryload  # type: ignore
from sqlalchemy import func, asc  # type: ignore
from typing import List
from app.utils import roles_required

STUDENT_OWNED_CATEGORY_SLUG = "student-owned"
STUDENT_OWNED_FILTER_ID = "student-owned"
STUDENT_OWNED_CATEGORY_NAME = "Student-Owned"
STUDENT_OWNED_CATEGORY_IMAGE = "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80"


@category.route('/all', methods=['GET'])
def get_all_categories():
    categories: List[Category] = db.session.query(Category).order_by(asc(Category.name)).all()
    category_data = [{
        'id': category.id,
        'name': category.name,
        'slug': category.slug,
        'imageURL': category.image_url,
        'offers': category.offer_count,
        'merchants': category.merchant_count,
    } for category in categories]

    student_owned_index = next(
        (idx for idx, item in enumerate(category_data)
         if item.get("slug") == STUDENT_OWNED_CATEGORY_SLUG),
        None
    )

    student_owned_offers = db.session.query(func.count(Offer.id)).join(
        Merchant, Offer.merchant_id == Merchant.id
    ).join(
        Category, Merchant.category_id == Category.id
    ).filter(
        Category.slug == STUDENT_OWNED_CATEGORY_SLUG
    ).scalar() or 0

    student_owned_merchants = db.session.query(func.count(Merchant.id)).join(
        Category, Merchant.category_id == Category.id
    ).filter(
        Category.slug == STUDENT_OWNED_CATEGORY_SLUG
    ).scalar() or 0

    if student_owned_index is None:

        category_data.insert(0, {
            "id": STUDENT_OWNED_FILTER_ID,
            "name": STUDENT_OWNED_CATEGORY_NAME,
            "slug": STUDENT_OWNED_CATEGORY_SLUG,
            "imageURL": STUDENT_OWNED_CATEGORY_IMAGE,
            "offers": student_owned_offers,
            "merchants": student_owned_merchants,
        })
    else:
        category_data[student_owned_index]["offers"] = student_owned_offers
        category_data[student_owned_index]["merchants"] = student_owned_merchants

    if student_owned_index is not None and student_owned_index != 0:
        student_owned = category_data.pop(student_owned_index)
        category_data.insert(0, student_owned)

    return jsonify({
        "message": "Get all categories",
        "data": category_data
    }), 200


@category.route('/<category_id>', methods=['GET'])
def get_category_by_id(category_id):
    """
    Get category by ID.
    Scenarios:
                    - Get category by ID
                    - Category not found
    """
    # Logic to get category by ID
    return jsonify({"message": f"Get category with ID {category_id}"}), 200


@category.route('/new', methods=['POST'])
@roles_required('admin')
def create_category():
    """
    Create a new category.
    Scenarios:
    - Create a new category
    - Category already exists
    - Missing required fields
    """
    # Logic to create a new category
    return jsonify({"message": "Create a new category"}), 201


@category.route('/<category_id>', methods=['PUT'])
@roles_required('admin')
def update_category(category_id):
    """
    Update a category.
    Scenarios:
                                    - Update a category
                                    - Category not found
                                    - Missing required fields
    """
    # Logic to update a category
    return jsonify({"message": f"Update category with ID {category_id}"}), 200


@category.route('/<category_id>', methods=['DELETE'])
@roles_required('admin')
def delete_category(category_id):
    """
    Delete a category.
    Scenarios:
                                    - Delete a category
                                    - Category not found
    """
    # Logic to delete a category
    return jsonify({"message": f"Delete category with ID {category_id}"}), 200


@category.route('/<category_id>/offers', methods=['GET'])
def get_products_by_category(category_id):
    """
    Get products by category.
    Scenarios:
                                    - Get products by category
                                    - Category not found
    """
    # Logic to get products by category
    return jsonify({"message": f"Get products for category with ID {category_id}"}), 200
