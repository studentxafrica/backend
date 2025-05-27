#!/usr/bin/env python3
# Module: Error handling for the API
from flask import Blueprint, jsonify, request

error = Blueprint('error', __name__)


@error.app_errorhandler(404)
def not_found(error):
    """
    Handle 404 errors.
    """
    return jsonify({
        "message": "Resource not found (404)",
        }), 404


@error.app_errorhandler(500)
def internal_server_error(error):
    """
    Handle 500 errors.
    """
    return jsonify({
        "message": f"Internal server error (500): {error.__str__()}",
        "description": "An unexpected error occurred on the server."
        }), 500


@error.app_errorhandler(401)
def unauthorized(error):
    """
    Handle 401 errors.
    """
    return jsonify({
        "message": "Unauthorized access (401)",
        }), 401


@error.app_errorhandler(403)
def forbidden(error):
    """
    Handle 403 errors.
    """
    return jsonify({
        "message": "Forbidden access (403)",
        }), 403


@error.app_errorhandler(400)
def bad_request(error):
    """
    Handle 400 errors.
    """
    return jsonify({
        "message": "Bad request (400)",
        }), 400


@error.app_errorhandler(405)
def method_not_allowed(error):
    """
    Handle 405 errors.
    """
    return jsonify({
        "message": "Method not allowed (405)",
        "description": f"The method ({request.method}) is not allowed for this resource."
        }), 405


@error.app_errorhandler(409)
def conflict(error):
    """
    Handle 409 errors.
    """
    return jsonify({
        "message": "Conflict (409)",
        "description": "The request could not be completed due to a conflict with the current state of the resource."
        }), 409


@error.app_errorhandler(422)
def unprocessable_entity(error):
    """
    Handle 422 errors.
    """
    return jsonify({
        "message": "Unprocessable entity (422)",
        "description": "The request was well-formed but was unable to be followed due to semantic errors."
        }), 422


@error.app_errorhandler(429)
def too_many_requests(error):
    """
    Handle 429 errors.
    """
    return jsonify({
        "message": "Too many requests (429)",
        "description": "You have sent too many requests. Please try again later."
    }), 429


@error.app_errorhandler(415)
def unsupported_media_type(error):
    """
    Handle 415 errors.
    """
    return jsonify({
        "message": "Unsupported media type (415)",
        "description": "The server does not support the media type transmitted in the request."
    }), 415


@error.app_errorhandler(408)
def request_timeout(error):
    """
    Handle 408 errors.
    """
    return jsonify({
        "message": "Request timeout (408)",
        "description": "The server timed out waiting for the request."
    }), 408
