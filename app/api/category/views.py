from . import category
from flask import jsonify, request
from app import db
from app.models.category import Category as Category
from sqlalchemy.orm import joinedload, subqueryload  # type: ignore
from typing import List


@category.route('/all', methods=['GET'])
def get_all_categories():
    categories: List[Category] = db.session.query(
        Category
    ).all()
    return jsonify({
        "message": "Get all categories",
        "data": [{
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'imageURL': category.image_url,
            'offers': category.offer_count,  # be precise
            'merchants': category.merchant_count,  # be precise
        } for category in categories]
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
