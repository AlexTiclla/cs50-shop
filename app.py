import os
import click
from flask import Flask, render_template
from dotenv import load_dotenv

load_dotenv()


def create_app(config_name=None):
    app = Flask(__name__)

    # Load config
    from config import config
    cfg_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config.get(cfg_name, config['default']))

    # Initialize extensions
    from extensions import db, login_manager
    db.init_app(app)
    login_manager.init_app(app)

    # Cart count available in all templates
    from flask_login import current_user

    @app.context_processor
    def inject_cart_count():
        if current_user.is_authenticated and not current_user.is_seller:
            from models import CartItem
            count = db.session.query(
                db.func.coalesce(db.func.sum(CartItem.quantity), 0)
            ).filter_by(user_id=current_user.id).scalar()
            return {'cart_count': int(count)}
        return {'cart_count': 0}

    # Ensure upload folder exists
    # upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    # os.makedirs(upload_path, exist_ok=True)

    # Register blueprints
    from blueprints.auth import auth
    from blueprints.shop import shop
    from blueprints.seller import seller

    app.register_blueprint(auth)
    app.register_blueprint(shop)
    app.register_blueprint(seller)

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template('500.html'), 500

    # CLI commands
    @app.cli.command('init-db')
    def init_db():
        """Create all database tables."""
        db.create_all()
        click.echo('Database tables created.')

    @app.cli.command('migrate-db')
    def migrate_db():
        """Add new columns/tables to existing schema (safe to run multiple times)."""
        from sqlalchemy import text

        def run(sql, ok_msg, skip_msg):
            with db.engine.connect() as conn:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    click.echo(ok_msg)
                except Exception as e:
                    msg = str(e).lower()
                    if 'already exists' in msg or 'duplicate column' in msg:
                        click.echo(skip_msg)
                    else:
                        click.echo(f'Migration error: {e}')

        run(
            "ALTER TABLE categories ADD COLUMN background_image_url VARCHAR(500)",
            'Added background_image_url to categories.',
            'Column background_image_url already exists, skipping.',
        )
        run(
            """CREATE TABLE cart_items (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                quantity INTEGER NOT NULL DEFAULT 1,
                added_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_cart_user_product UNIQUE (user_id, product_id)
            )""",
            'Created cart_items table.',
            'Table cart_items already exists, skipping.',
        )

    @app.cli.command('seed-db')
    def seed_db():
        """Create admin seller account if none exists."""
        from models import User
        if not User.query.filter_by(role='seller').first():
            admin = User(username='admin', email='admin@example.com', role='seller')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            click.echo('Admin seller account created: admin / admin123')
        else:
            click.echo('A seller account already exists.')

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
