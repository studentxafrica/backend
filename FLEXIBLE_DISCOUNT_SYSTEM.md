# Flexible Discount System Implementation

## Overview
The flexible discount system has been implemented to replace the rigid "one coupon per offer per student" model with a more versatile approach that supports multiple usage patterns.

## Key Components Implemented

### 1. New Database Models

#### UserOfferUsage Model (`app/models/user_offer_usage.py`)
Tracks detailed usage statistics for each user-offer combination:
- `usage_count`: Number of times user has claimed coupons for this offer
- `total_savings`: Total amount saved in cents
- `total_redemptions`: Number of times coupons were actually redeemed
- `first_claimed_at`, `last_claimed_at`, `last_redemption_at`: Timestamps
- `average_days_between_usage`: Usage frequency analytics

#### Enhanced Offer Model
New fields added to support flexible usage:
- `usage_type`: single_use, multi_use, unlimited, or tiered
- `max_claims_per_user`: Maximum claims for multi_use/tiered offers
- `cooldown_period_hours`: Time between claims
- `tier_progression`: JSON configuration for tiered discounts

### 2. Usage Types Supported

#### Single Use (Default)
- Traditional behavior: one coupon per offer per user
- Backward compatible with existing offers

#### Multi Use
- Users can claim up to `max_claims_per_user` times
- Optional cooldown period between claims
- Example: "Get 20% off up to 3 times per month"

#### Unlimited
- No limit on number of claims
- Optional cooldown period only
- Example: "Daily coffee discount"

#### Tiered
- Progressive discounts based on usage frequency
- JSON-configured tier rules
- Example: Bronze (10%), Silver (15%), Gold (20%) based on usage count

### 3. New API Endpoints

#### Usage Statistics
```
GET /api/offers/{id}/usage-stats
```
Get detailed usage statistics for a specific offer and current user.

#### Savings Summary
```
GET /api/offers/user/savings-summary
```
Comprehensive savings summary across all offers for current user.

#### Available Claims Check
```
GET /api/offers/{id}/available-claims
```
Check how many more times user can claim a specific offer.

### 4. Updated Endpoints

#### Create Offer (`POST /api/offers/new`)
Now accepts new fields:
- `usage_type` (optional, defaults to 'single_use')
- `max_claims_per_user` (required for multi_use)
- `cooldown_period_hours` (optional)
- `tier_progression` (optional JSON for tiered offers)

#### Claim Coupon (`POST /api/offers/{id}/coupons/create`)
- Uses flexible validation instead of rigid one-coupon check
- Returns usage statistics and tiered discount information
- Provides cooldown and remaining claims info

#### Redeem Coupon (`POST /api/coupons/{id}/redeem`)
- Tracks savings amounts and redemption statistics
- Updates usage analytics automatically

## Database Migration

A migration has been created to add the new schema:
```bash
flask db upgrade
```

This will:
1. Add new fields to the `offers` table
2. Create the `user_offer_usage` table
3. Add appropriate indexes for performance

## Example Usage

### Creating a Multi-Use Offer
```json
{
  "title": "Coffee Shop Discount",
  "description": "20% off your coffee order",
  "usage_type": "multi_use",
  "max_claims_per_user": 5,
  "cooldown_period_hours": 24,
  "discount_type": "percentage",
  "discount_value": 20,
  // ... other required fields
}
```

### Creating a Tiered Offer
```json
{
  "title": "Loyalty Restaurant Discount",
  "description": "Progressive discounts for frequent diners",
  "usage_type": "tiered",
  "max_claims_per_user": 10,
  "tier_progression": {
    "tiers": [
      {"min_usage": 0, "discount_multiplier": 1.0, "name": "Bronze"},
      {"min_usage": 3, "discount_multiplier": 1.5, "name": "Silver"}, 
      {"min_usage": 6, "discount_multiplier": 2.0, "name": "Gold"}
    ]
  },
  "discount_type": "percentage",
  "discount_value": 10,
  // ... other required fields
}
```

## Benefits Delivered

### For Students
- **Multiple claims**: Can use favorite offers repeatedly
- **Loyalty rewards**: Better discounts with frequent usage (tiered offers)
- **Usage tracking**: See total savings and claim history
- **Flexible timing**: Cooldown periods instead of permanent restrictions

### For Merchants
- **Customer retention**: Multi-use offers encourage repeat visits
- **Flexible pricing**: Adjust limits and cooldowns based on business needs
- **Better analytics**: Detailed usage and redemption tracking
- **Seasonal control**: Time-based restrictions and progressive rewards

### For Platform
- **Increased engagement**: Users return more frequently
- **Rich analytics**: Detailed usage patterns and savings data
- **Flexible business models**: Support diverse merchant strategies
- **Backward compatibility**: Existing offers continue to work

## Implementation Status

✅ **Completed:**
- Database schema and migration
- Core usage validation logic
- API endpoint updates
- Usage tracking and analytics
- Tiered discount calculations
- Helper functions and utilities

🔄 **Next Steps (Optional Enhancements):**
- Admin interface updates for offer creation
- Frontend UI components for usage display
- Advanced analytics dashboard
- Push notifications for cooldown expiry
- Bulk offer management tools

## Testing the System

1. **Run the migration:**
   ```bash
   flask db upgrade
   ```

2. **Test offer creation with new usage types via API**

3. **Test coupon claiming with different usage scenarios**

4. **Verify usage statistics endpoints**

The system is fully backward compatible - existing single-use offers will continue to work exactly as before, while new offers can take advantage of the flexible usage patterns.