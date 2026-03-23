# CS50 Shop
#### Video Demo: [Link of the video](https://youtu.be/Dse_3R6S7wE)
#### Description:
A full-stack e-commerce web application. There are two kinds of user: customer and seller (admin).
The seller can manage products, categories, and also create another seller account. One feature is that the saller can download a PDF of the product title, categorie, price, and an AI description generated.
The client can view the catalog, and add products to their carts, but they can't actually buy things, they are referred to the seller's whatsapp with the list of products they are interested in.
#### You can visit CS50 Shop: [Vercel Link](https://cs50-shop.vercel.app/)

#### Technology Stack:
Supabase (Postgres) for the Database.
Cloudinary for storing the images of the site.
The project was deployed in Vercel.
Flask for the backend.
SQLAlchemy as the ORM (Object Relation Mapping)
HTML, CSS, Bootstrap, for the design of the Frontend.
JavaScript for managing the interactivity with a share button.
Gemini AI for generating description of products.

#### Explaining file's contents
##### **models.py**: 
It contains four main classes `User` representing a user in the database and their relationships.
`Product` representing the product table.
`CartItem` representing the customer's cart.
`Category` representing the category of a product.

##### **extensions.py**:
Is where SQLAlchemy and LoginManager are initialized.
```
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
db = SQLAlchemy()
login_manager = LoginManager()
```

##### **config.py**:
This is where `.env` environment variables are called and stored in variables.
We also define configuration in development `DevelopmentConfig`and production `ProductionConfig`

##### **templates**:
This is where all the HTML templates are placed in.  
All of these below, they *extend* from `base.html`
###### **auth**:
Folder that contains the main forms for `login.html` and `register.html`.

###### **cart**:
`cart.html` shows the cart content in a table of products.

###### **seller**:
Folder exclusive for the seller role view.

##### **static**:
css (`main.css`) and js `cart.js` files are stored in this folder.
**important**: the folder called `uploads` was where all the product's images where saved. But, then I migrate to Cloudinary.

##### **blueprints**:
Here are the routes, endpoints in three main files.
*Backend side logic*.

1. `auth.py`: endpoints for only authentication purposes.
2. `seller.py`: seller's exclusive endpoints, 
operation logic for creating, reading, updating, and deleting products and categories.
3. `shop.py`: here there are endpoints for customer's operations like
    - `@shop.route('/')` for viewing the *index* page for the customer.
    - `@shop.route('/product/<slug>')` for rendering the product with its slug.
    - `@shop.route('/cart/add', methods=['POST'])` for adding a product to the car. A new row in CartItem with the `current_user.id`, `product_id`, `quantity`
    - `@shop.route('/cart')` for rendering the cart.html and viewing all the products in the customer's cart.
    - `@shop.route('/cart/update', methods=['POST'])` for updating the cart.
    - `@shop.route('/cart/remove', methods=['POST'])` for removing a product from the cart.
    - `@shop.route('/cart/whatsapp')` main purpose is to redirect to the seller's whatsapp with the description of the customer's cart.