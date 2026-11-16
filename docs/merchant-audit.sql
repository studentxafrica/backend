-- Merchants and their offers, oldest account first.
-- Read-only. Run against production before deploying the approval filter:
-- any merchant with live_offers > 0 and approved_on IS NULL will have those
-- offers hidden from students until an administrator approves it.

SELECT
    m.id,
    m.name,
    m.email,
    m.created_at,
    m.approved_on,
    m.email_verified_on,
    COUNT(o.id) AS total_offers,
    SUM(CASE WHEN o.status = 'active' AND o.end_date > UTC_TIMESTAMP() THEN 1 ELSE 0 END) AS live_offers
FROM merchants m
LEFT JOIN offers o ON o.merchant_id = m.id
GROUP BY m.id, m.name, m.email, m.created_at, m.approved_on, m.email_verified_on
ORDER BY m.created_at;
