# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

E-commerce web app (CS50 final project) with two roles: **customer** and **seller**. No payment processing — purchases are handled by redirecting to WhatsApp. Keep it simple.

**Customer capabilities:**
- Browse products without logging in
- Register and log in
- Add products to a cart
- Send cart contents as a single WhatsApp message to the seller

**Seller capabilities (admin role):**
- Full CRUD for products and categories
- View private product data (stock, cost price)
- Export a product to PDF (image, title, price, description)
- Share a product via WhatsApp with an AI-generated description
- Create other seller accounts

## Tech Stack

- **Backend:** Python, Flask, SQLAlchemy
- **Database:** PostgreSQL
- **Frontend:** HTML, CSS, JavaScript, Bootstrap
- **AI:** Used to generate product descriptions for WhatsApp sharing

## Setup & Running

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows/Git Bash
pip install -r requirements.txt

python app.py
```

App runs at http://localhost:5000 with debug mode enabled.
