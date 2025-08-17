# from flask_restx import Api

# api = Api(
#     title='StudentX API',
#     version='1.0',
#     description='A comprehensive API for the StudentX platform',
#     doc='/api/docs',
#     prefix='/api/v1'
# )

# # Import and register namespaces here
# from .admin import admin as admin_ns
# from .auth import auth as auth_ns
# from .category import category as category_ns
# from .coupon import coupon as coupons_ns
# from .offer import offer as offers_ns
# from .store import store as merchants_ns
# from .user import user as consumers_ns

# # Register namespaces
# api.add_namespace(auth_ns, path='/auth')
# api.add_namespace(offers_ns, path='/offers')
# api.add_namespace(merchants_ns, path='/merchants')
# api.add_namespace(consumers_ns, path='/consumers')
# api.add_namespace(coupons_ns, path='/coupons')
# api.add_namespace(category_ns, path='/categories')
# api.add_namespace(admin_ns, path='/admin')
