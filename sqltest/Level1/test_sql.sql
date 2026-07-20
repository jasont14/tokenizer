/* Complex SQL query with join, aggregation, and filtering */

SELECT 
    c.customer_name,
    COUNT(o.order_id) as order_count,
    SUM(oi.amount) as total_spent
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
LEFT JOIN customer_master oi ON o.id = oi.order_id
WHERE c.country = 'US'
GROUP BY c.customer_name
HAVING COUNT(o.order_id) > 5
ORDER BY total_spent DESC;