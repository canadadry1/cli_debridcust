# File: godver3/cli_debrid/cli_debrid-c51ff53e5123ef56c2eb4bcb3e5f00dbae792c0d/routes/database_routes.py

from flask import jsonify, request, render_template, session, flash, Blueprint, current_app
import sqlite3
import string
from database import get_db_connection, get_all_media_items, update_media_item_state
import logging
from sqlalchemy import text, inspect
from extensions import db
from database import remove_from_media_items # This might still be used elsewhere, but not for granular deletion
from settings import get_setting
import json
from reverse_parser import get_version_settings, get_default_version, get_version_order, parse_filename_for_version
from .models import admin_required
from utilities.plex_functions import remove_file_from_plex # This might still be used elsewhere
from database.database_reading import get_media_item_by_id # This might still be used elsewhere
import os
from datetime import datetime
from time import sleep

# Import necessary Flask-Login components
from flask_login import login_required, current_user

# Import the new comprehensive deletion function
from database.maintenance import delete_media_item_and_symlink_and_db_entry

# Define the Blueprint. Using 'database_bp' for consistency with the new route.
database_bp = Blueprint('database_bp', __name__)
logger = logging.getLogger(__name__)


@database_bp.route('/api/media_items/<int:item_id>', methods=['DELETE'])
@login_required # Ensures only authenticated users can access
@admin_required # Ensures only admin users can access (assuming this decorator works with Flask-Login)
def delete_media_item_api(item_id):
    """
    API endpoint to delete a single media item from the database,
    its associated symlink, and relevant verification entries.
    Requires admin privileges.
    """
    # The admin_required decorator should handle the authorization,
    # but an explicit check can be kept for clarity or if decorator is not fully implemented.
    if not current_user.is_authenticated or not current_user.is_admin:
        logger.warning(f"Unauthorized attempt to delete media item ID: {item_id} by user: {current_user.id if current_user.is_authenticated else 'anonymous'}")
        return jsonify({'error': 'Unauthorized: Admin access required.'}), 403

    try:
        # Call the comprehensive deletion function
        success = delete_media_item_and_symlink_and_db_entry(item_id)
        
        if success:
            logger.info(f"User {current_user.username} successfully deleted media item ID: {item_id} (and symlink if existed).")
            return jsonify({'message': f'Media item {item_id} deleted successfully.'}), 200
        else:
            logger.warning(f"Media item ID: {item_id} not found or could not be deleted.")
            return jsonify({'error': f'Media item {item_id} not found or could not be deleted.'}), 404
            
    except Exception as e:
        logger.error(f"Error deleting media item {item_id}: {e}", exc_info=True)
        return jsonify({'error': f'An error occurred during deletion: {str(e)}'}), 500


@database_bp.route('/', methods=['GET', 'POST'])
@admin_required
def index():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all column names
        cursor.execute("PRAGMA table_info(media_items)")
        all_columns = [column[1] for column in cursor.fetchall()]

        # Define the default columns
        default_columns = [
            'imdb_id', 'title', 'year', 'release_date', 'state', 'type',
            'season_number', 'episode_number', 'collected_at', 'version'
        ]

        # Get or set selected columns
        if request.method == 'POST':
            selected_columns = request.form.getlist('columns')
            session['selected_columns'] = selected_columns
        else:
            selected_columns = session.get('selected_columns')

        # If no columns are selected, use the default columns
        if not selected_columns:
            selected_columns = [col for col in default_columns if col in all_columns]
            if not selected_columns:
                selected_columns = ['id']  # Fallback to ID if none of the default columns exist

        # Ensure at least one column is selected
        if not selected_columns:
            selected_columns = ['id']

        # Get filter and sort parameters
        filter_column = request.args.get('filter_column', '')
        filter_value = request.args.get('filter_value', '')
        sort_column = request.args.get('sort_column', 'id')  # Default sort by id
        sort_order = request.args.get('sort_order', 'asc')
        content_type = request.args.get('content_type', 'movie')  # Default to 'movie'
        current_letter = request.args.get('letter', 'A')

        # Validate sort_column
        if sort_column not in all_columns:
            sort_column = 'id'  # Fallback to 'id' if invalid column is provided

        # Validate sort_order
        if sort_order.lower() not in ['asc', 'desc']:
            sort_order = 'asc'  # Fallback to 'asc' if invalid order is provided

        # Define alphabet here
        alphabet = list(string.ascii_uppercase)

        # Construct the SQL query
        query = f"SELECT {', '.join(selected_columns)} FROM media_items"
        where_clauses = []
        params = []

        # Apply custom filter if present, otherwise apply content type and letter filters
        if filter_column and filter_value:
            where_clauses.append(f"{filter_column} LIKE ?")
            params.append(f"%{filter_value}%")
            # Reset content_type and current_letter when custom filter is applied
            content_type = 'all'
            current_letter = ''
        else:
            if content_type != 'all':
                where_clauses.append("type = ?")
                params.append(content_type)
            
            if current_letter:
                if current_letter == '#':
                    where_clauses.append("title LIKE '0%' OR title LIKE '1%' OR title LIKE '2%' OR title LIKE '3%' OR title LIKE '4%' OR title LIKE '5%' OR title LIKE '6%' OR title LIKE '7%' OR title LIKE '8%' OR title LIKE '9%' OR title LIKE '[%' OR title LIKE '(%' OR title LIKE '{%'")
                elif current_letter.isalpha():
                    where_clauses.append("title LIKE ?")
                    params.append(f"{current_letter}%")

        # Construct the ORDER BY clause safely
        order_clause = f"ORDER BY {sort_column} {sort_order}"

        # Ensure 'id' is always included in the query, even if not displayed
        query_columns = list(set(selected_columns + ['id']))
        
        # Construct the final query
        query = f"SELECT {', '.join(query_columns)} FROM media_items"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += f" {order_clause}"

        # Log the query and parameters for debugging
        logging.debug(f"Executing query: {query}")
        logging.debug(f"Query parameters: {params}")

        # Execute the query
        cursor.execute(query, params)
        items = cursor.fetchall()

        # Log the number of items fetched
        logging.debug(f"Fetched {len(items)} items from the database")

        conn.close()

        # Convert items to a list of dictionaries, always including 'id'
        items = [dict(zip(query_columns, item)) for item in items]

        # Prepare the data dictionary
        data = {
            'items': items,
            'all_columns': all_columns,
            'selected_columns': selected_columns,
            'filter_column': filter_column,
            'filter_value': filter_value,
            'sort_column': sort_column,
            'sort_order': sort_order,
            'alphabet': alphabet,
            'current_letter': current_letter,
            'content_type': content_type
        }

        if request.args.get('ajax') == '1':
            return jsonify(data)
        else:
            return render_template('database.html', **data)
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error in database route: {str(e)}")
        error_message = f"Database error: {str(e)}"
    except Exception as e:
        logging.error(f"Unexpected error in database route: {str(e)}")
        error_message = "An unexpected error occurred. Please try again later."

    if request.args.get('ajax') == '1':
        return jsonify({'error': error_message}), 500
    else:
        flash(error_message, "error")
        # Remove 'items' from the arguments here
        return render_template('database.html', **{**data, 'items': []})

@database_bp.route('/bulk_queue_action', methods=['POST'])
@login_required
@admin_required
def bulk_queue_action():
    action = request.form.get('action')
    target_queue = request.form.get('target_queue')
    selected_items = request.form.getlist('selected_items')
    # The 'blacklist' parameter from the old delete_item is not directly used here
    # as delete_media_item_and_symlink_and_db_entry handles full deletion.
    # If a 'blacklist only' action is desired, it would need a separate function.

    if not action or not selected_items:
        return jsonify({'success': False, 'error': 'Action and selected items are required'})

    # Process items in batches to avoid SQLite parameter limits
    BATCH_SIZE = 450  # Stay well under SQLite's 999 parameter limit
    total_processed = 0
    error_count = 0
    errors = []
    
    try:
        if action == 'delete':
            # Process each item in the batch through the new comprehensive delete function
            for item_id_str in selected_items:
                try:
                    item_id = int(item_id_str)
                    success = delete_media_item_and_symlink_and_db_entry(item_id)
                    if success:
                        total_processed += 1
                    else:
                        error_count += 1
                        errors.append(f"Error processing item {item_id}: Item not found or could not be deleted.")
                except ValueError:
                    error_count += 1
                    errors.append(f"Invalid item ID format: {item_id_str}")
                    logging.error(f"Invalid item ID format in bulk delete: {item_id_str}")
                except Exception as e:
                    error_count += 1
                    errors.append(f"Error processing item {item_id_str}: {str(e)}")
                    logging.error(f"Error processing item {item_id_str} in bulk delete: {str(e)}")
                        
        elif action == 'move' and target_queue:
            # Keep existing move functionality
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(selected_items))
                cursor.execute(
                    f'UPDATE media_items SET state = ?, last_updated = ? WHERE id IN ({placeholders})',
                    [target_queue, datetime.now()] + selected_items
                )
                total_processed += cursor.rowcount
                conn.commit()
            except Exception as e:
                error_count += 1
                conn.rollback()
                errors.append(f"Error in batch: {str(e)}")
                logging.error(f"Error in batch: {str(e)}")
            finally:
                conn.close()
        elif action == 'change_version' and target_queue:  # target_queue contains the version in this case
            conn = get_db_connection()
            try:
                    cursor = conn.cursor()
                    placeholders = ','.join('?' * len(selected_items))
                    cursor.execute(
                        f'UPDATE media_items SET version = ?, last_updated = ? WHERE id IN ({placeholders})',
                        [target_queue, datetime.now()] + selected_items
                    )
                    total_processed += cursor.rowcount
                    conn.commit()
            except Exception as e:
                error_count += 1
                conn.rollback()
                errors.append(f"Error in batch: {str(e)}")
                logging.error(f"Error in batch: {str(e)}")
            finally:
                conn.close()
        elif action == 'early_release':
            # Handle early release action
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(selected_items))
                cursor.execute(
                    f'UPDATE media_items SET early_release = TRUE, state = ?, last_updated = ? WHERE id IN ({placeholders})',
                    ['Wanted', datetime.now()] + selected_items
                )
                total_processed += cursor.rowcount
                conn.commit()
            except Exception as e:
                error_count += 1
                conn.rollback()
                errors.append(f"Error in batch: {str(e)}")
                logging.error(f"Error in batch: {str(e)}")
            finally:
                conn.close()
        else:
            return jsonify({'success': False, 'error': 'Invalid action or missing target queue'})

        if error_count > 0:
            message = f"Completed with {error_count} errors. Successfully processed {total_processed} items."
            if errors:
                message += f" First few errors: {'; '.join(errors[:3])}"
            return jsonify({'success': True, 'message': message, 'warning': True})
        else:
            action_text = "deleted" if action == "delete" else "moved to {target_queue} queue" if action == "move" else "marked as early release and moved to Wanted queue" if action == "early_release" else f"changed to version {target_queue}"
            message = f"Successfully {action_text} {total_processed} items"
            return jsonify({'success': True, 'message': message})

    except Exception as e:
        logging.error(f"Error performing bulk action: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Removed the old delete_item route as it's superseded by delete_media_item_api
# and delete_media_item_and_symlink_and_db_entry.

def perform_database_migration():
    # logging.info("Performing database migration...")
    inspector = inspect(db.engine)
    if not inspector.has_table("user"):
        # If the user table doesn't exist, create all tables
        db.create_all()
    else:
        # Check if onboarding_complete column exists
        columns = [c['name'] for c in inspector.get_columns('user')]
        if 'onboarding_complete' not in columns:
            # Add onboarding_complete column
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN onboarding_complete BOOLEAN DEFAULT FALSE"))
                conn.commit()
    
    # Commit the changes
    db.session.commit()

@database_bp.route('/reverse_parser', methods=['GET', 'POST'])
def reverse_parser():
    logging.debug("Entering reverse_parser function")
    data = {
        'selected_columns': ['title', 'filled_by_file', 'version'],
        'sort_column': 'title',
        'sort_order': 'asc'
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        page = int(request.args.get('page', 1))
        items_per_page = 100
        filter_default = request.args.get('filter_default', 'false').lower() == 'true'

        logging.debug(f"page: {page}, items_per_page: {items_per_page}, filter_default: {filter_default}")

        # Fetch the latest settings every time
        version_terms = get_version_settings()
        default_version = get_default_version()
        version_order = get_version_order()

        # Construct the base query
        query = f"""
            SELECT id, {', '.join(data['selected_columns'])}
            FROM media_items
            WHERE state = 'Collected'
        """
        
        params = []

        # Add filtering logic
        if filter_default:
            version_conditions = []
            for version, terms in version_terms.items():
                if terms:
                    term_conditions = " OR ".join(["filled_by_file LIKE ?" for _ in terms])
                    version_conditions.append(f"({term_conditions})")
                    params.extend([f"%{term}%" for term in terms])
            
            if version_conditions:
                query += f" AND NOT ({' OR '.join(version_conditions)})"

        # Add sorting and pagination
        query += f" ORDER BY {data['sort_column']} {data['sort_order']}"
        query += f" LIMIT {items_per_page} OFFSET {(page - 1) * items_per_page}"

        logging.debug(f"Executing query: {query}")
        logging.debug(f"Query parameters: {params}")

        cursor.execute(query, params)
        items = cursor.fetchall()

        logging.debug(f"Fetched {len(items)} items from the database")

        conn.close()

        items = [dict(zip(['id'] + data['selected_columns'], item)) for item in items]

        # Parse versions using parse_filename_for_version function
        for item in items:
            parsed_version = parse_filename_for_version(item['filled_by_file'])
            item['parsed_version'] = parsed_version
            logging.debug(f"Filename: {item['filled_by_file']}, Parsed Version: {parsed_version}")

        data.update({
            'items': items,
            'page': page,
            'filter_default': filter_default,
            'default_version': default_version,
            'version_terms': version_terms,
            'version_order': version_order
        })

        if request.args.get('ajax') == '1':
            return jsonify(data)
        else:
            return render_template('reverse_parser.html', **data)
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error in reverse_parser route: {str(e)}")
        error_message = f"Database error: {str(e)}"
    except Exception as e:
        logging.error(f"Unexpected error in reverse_parser route: {str(e)}")
        error_message = "An unexpected error occurred. Please try again later."

    if request.args.get('ajax') == '1':
        return jsonify({'error': error_message}), 500
    else:
        flash(error_message, "error")
        return render_template('reverse_parser.html', **data)
    
@database_bp.route('/apply_parsed_versions', methods=['POST'])
def apply_parsed_versions():
    try:
        items = get_all_media_items()
        updated_count = 0
        for item in items:
            if item['filled_by_file']:
                parsed_version = parse_filename_for_version(item['filled_by_file'])
                
                # Only update if the parsed version is different from the current version
                current_version = item['version'] if 'version' in item.keys() else None
                if parsed_version != current_version:
                    try:
                        update_media_item_state(item['id'], item['state'], version=parsed_version)
                        updated_count += 1
                    except Exception as e:
                        logging.error(f"Error updating item {item['id']}: {str(e)}")
        
        return jsonify({
            'success': True, 
            'message': f'Parsed versions applied successfully. Updated {updated_count} items.'
        })
    except Exception as e:
        logging.error(f"Error applying parsed versions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@database_bp.route('/watch_history', methods=['GET'])
@admin_required
def watch_history():
    try:
        # Get database connection
        db_dir = os.environ.get('USER_DB_CONTENT', '/user/db_content')
        db_path = os.path.join(db_dir, 'watch_history.db')
        
        if not os.path.exists(db_path):
            flash("Watch history database not found. Please sync Plex watch history first.", "warning")
            return render_template('watch_history.html', items=[])
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get filter parameters
        content_type = request.args.get('type', 'all')  # 'movie', 'episode', or 'all'
        sort_by = request.args.get('sort', 'watched_at')  # 'title' or 'watched_at'
        sort_order = request.args.get('order', 'desc')  # 'asc' or 'desc'
        
        # Build query
        query = """
            SELECT title, type, watched_at, season, episode, show_title, source
            FROM watch_history
            WHERE 1=1
        """
        params = []
        
        if content_type != 'all':
            query += " AND type = ?"
            params.append(content_type)
            
        query += f" ORDER BY {sort_by} {sort_order}"
        
        # Execute query
        cursor.execute(query, params)
        items = cursor.fetchall()
        
        # Convert to list of dicts for easier template handling
        formatted_items = []
        for item in items:
            title, type_, watched_at, season, episode, show_title, source = item
            
            # Format the watched_at date
            try:
                watched_at = datetime.strptime(watched_at, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M')
            except:
                watched_at = 'Unknown'
                
            # Format the display title
            if type_ == 'episode' and show_title:
                display_title = f"{show_title} - S{season:02d}E{episode:02d} - {title}"
            else:
                display_title = title
                
            formatted_items.append({
                'title': display_title,
                'type': type_,
                'watched_at': watched_at,
                'source': source
            })
        
        conn.close()
        
        return render_template('watch_history.html',
                             items=formatted_items,
                             content_type=content_type,
                             sort_by=sort_by,
                             sort_order=sort_order)
                             
    except Exception as e:
        logging.error(f"Error in watch history route: {str(e)}")
        flash(f"Error retrieving watch history: {str(e)}", "error")
        return render_template('watch_history.html', items=[])

@database_bp.route('/watch_history/clear', methods=['POST'])
@admin_required
def clear_watch_history():
    try:
        # Get database connection
        db_dir = os.environ.get('USER_DB_CONTENT', '/user/db_content')
        db_path = os.path.join(db_dir, 'watch_history.db')
        
        if not os.path.exists(db_path):
            return jsonify({'success': False, 'error': 'Watch history database not found'})
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Clear the watch history table
        cursor.execute('DELETE FROM watch_history')
        
        # Reset the auto-increment counter
        cursor.execute('DELETE FROM sqlite_sequence WHERE name = "watch_history"')
        
        conn.commit()
        conn.close()
        
        logging.info("Watch history cleared successfully")
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Error clearing watch history: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})