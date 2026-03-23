# Design Document — CS50 Shop

## Database Schema Decisions

The schema consists of three tables: `users`, `categories`, and `products`.

**User roles** are stored as a plain `VARCHAR` column (`'customer'` or `'seller'`) rather than a separate `roles` table. With only two roles and no need for role combinations or runtime role management, a string column is the simplest and most readable solution. A separate roles table would add a join without any benefit at this scale.

**Slugs** are generated from the product/category name (lowercased, punctuation removed, spaces replaced by hyphens) and stored in the database. Generating slugs on the fly at query time would require a database function and make filtering/ordering harder. Storing them makes URL routing a single indexed lookup.

**Cost price and stock** are on the `Product` model alongside public fields. Separating them into a `product_private_data` table would normalize the schema but add unnecessary complexity. Instead, the application layer enforces visibility — these fields are never passed to shop-facing templates. This is verified during development by inspecting rendered HTML source.

---

## Cart: Session vs. Database Table

The cart is stored in the Flask session (`session['cart'] = {product_id_str: quantity_int}`) rather than a `cart_items` table for several reasons:

1. **Simplicity**: No schema changes, no migrations, no ORM queries for every page load.
2. **No login required to browse**: A session-based cart works before authentication. (In this app customers must log in to add items, but the pattern is extensible.)
3. **CS50 scope**: The project doesn't require persistence across devices or browsers. A single-device session is sufficient.
4. **Cleanup is automatic**: Sessions expire; orphaned cart rows in a DB table would need a cleanup job.

The trade-off is that carts are lost when sessions expire or cookies are cleared. For a production system with persistent carts, a `cart_items` table linked to the user would be preferable.

---

## WhatsApp Instead of a Payment Gateway

Integrating Stripe, PayPal, or MercadoPago requires a business account, webhook infrastructure, SSL certificates in production, and compliance considerations. For a CS50 project selling through a personal/small business context, the WhatsApp flow is a better fit:

- The seller already communicates with customers on WhatsApp.
- No payment credentials or PCI compliance needed.
- The `wa.me` deep-link API is free, reliable, and works on all devices.
- The seller can negotiate, confirm stock, and arrange delivery in the same conversation.

The implementation uses `urllib.parse.quote()` to encode the order summary into a pre-filled WhatsApp message. The seller's number is configured via the `SELLER_WHATSAPP` environment variable so it's never hardcoded.

---

## Blueprint Architecture

The app is split into three blueprints:

- **`auth`** (`/auth/`): Registration, login, logout. Stateless forms, no database reads beyond user lookup.
- **`shop`** (`/`, `/product/`, `/cart/`): Public-facing catalog and customer cart. Never exposes seller-only data.
- **`seller`** (`/seller/`): All seller functionality behind the `seller_required` decorator. Isolated from shop routes to make access control explicit and auditable.

Using an app factory (`create_app()`) instead of a global `app` object avoids circular imports, allows multiple app instances (e.g., testing), and follows Flask best practices.

---

## Protecting Seller-Only Data

Two mechanisms protect `cost_price` and `stock` from customers:

1. **Route-level**: The `seller_required` decorator (wrapping `@login_required` + `current_user.is_seller` check) gates all `/seller/` endpoints. A customer hitting those routes gets a 403.
2. **Template-level**: Shop templates (`index.html`, `product.html`, `cart/cart.html`) are written to never reference `cost_price` or `stock`. There is no route that serializes a Product to JSON for the shop frontend, so there's no accidental exposure through an API response.

This defense-in-depth approach means a bug in one layer (e.g., accidentally passing the full product object to a shop template) doesn't automatically expose sensitive data if the template doesn't render those fields.
