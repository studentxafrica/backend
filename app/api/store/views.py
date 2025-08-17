from . import store
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.merchant import Merchant
from app.models.store import Store
from app import db
from flask import request, jsonify, g
from app.utils import roles_required
from typing import List


@store.route('/new', methods=['POST'])
@roles_required('merchant')
def create_new_store():
    """
    Create a new store.
    Scenarios:
    - Create a store with valid data
    - Create a store with missing required fields
    - Create a store with invalid data types
    """
    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing JSON in request"}), 400
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({"message": "Unauthorized"}), 401
    store = db.session.query(Store).filter(
        Store.merchant_id == merchant.id,
        Store.name == data.get('name')
    ).first()

    if store:
        return jsonify({"message": "Store with this name already exists"}), 400

    ACCEPTED_FIELDS = [
        'name', 'location', 'contact_email', 'contact_phone', 'manager_name'
    ]
    store_data = {field: data.get(field)
                  for field in ACCEPTED_FIELDS if field in data}
    if not store_data:
        return jsonify({"message": "No valid store data provided"}), 400
    if not store_data.get('name') or not store_data.get('location') or not store_data.get('contact_email'):
        return jsonify({"message": "Missing required fields"}), 400

    new_store = Store(**store_data, merchant=merchant)
    new_store.save()
    return jsonify({
        "message": "Store created successfully",
        "data": {
            "id": new_store.id,
            "name": new_store.name,
            "location": new_store.location,
            "contactEmail": new_store.contact_email,
            "contactPhone": new_store.contact_phone,
            "managerName": new_store.manager_name
        }}), 201


@store.route('/merchant/all', methods=['GET'])
@roles_required('merchant')
def get_merchant_stores():
    """
    Get all stores for the authenticated merchant.
    Scenarios:
    - Get all stores successfully
    - No stores found for the merchant
    """
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({
            "message": "Unauthorized merchant",
            "description": "You must be logged in as a merchant to access this resource."
        }), 401

    store_list: List[Store] = [{
        "id": store.id,
        "name": store.name,
        "location": store.location,
        "contactEmail": store.contact_email,
        "contactPhone": store.contact_phone,
        "managerName": store.manager_name
    } for store in merchant.stores if merchant.stores]

    return jsonify({
        "message": "Stores retrieved successfully",
        "data": store_list
    }), 200


@store.route('/<id>', methods=['DELETE'])
@roles_required('merchant')
def delete_store(id):
    """
    Delete a store by ID.
    Scenarios:
    - Delete a store successfully
    - Store not found
    - Unauthorized access
    """
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({"message": "Unauthorized"}), 401

    store: Store = db.session.query(Store).filter(
        Store.id == id,
        Store.merchant_id == merchant.id
    ).first()

    if not store:
        return jsonify({"message": "Store not found in your account"}), 404

    store.delete()

    return jsonify({
        "message": "Store deleted successfully"
    }), 200
