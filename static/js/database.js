// File: godver3/cli_debrid/cli_debrid-c51ff53e5123ef56c2eb4bcb3e5f00dbae792c0d/static/js/database.js

document.addEventListener('DOMContentLoaded', function() {
    const confirmationModal = document.getElementById('confirmationModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalMessage = document.getElementById('modalMessage');
    const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');

    let currentItemIdToDelete = null;
    let currentItemTitleToDelete = null;

    // --- Utility Functions (Placeholders - implement these in base.js or notifications.js) ---
    // These functions are assumed to exist globally or imported from other scripts.
    // For testing, they will just log to console or use alert().
    function showNotification(message, type = 'info') {
        // Example implementation (replace with your actual notification system)
        console.log(`Notification (${type}): ${message}`);
        // You might use a library or custom div for notifications
        // e.g., document.getElementById('app-notification-area').innerHTML = `<div class="${type}">${message}</div>`;
        // For now, using alert for immediate feedback
        alert(message);
    }

    function showLoadingIndicator(message = 'Processing...') {
        // Example implementation (replace with your actual loading indicator)
        console.log(`Loading: ${message}`);
        // e.g., document.getElementById('loading-spinner').style.display = 'block';
        // For now, just logging
    }

    function hideLoadingIndicator() {
        // Example implementation (replace with your actual loading indicator)
        console.log('Loading finished.');
        // e.g., document.getElementById('loading-spinner').style.display = 'none';
        // For now, just logging
    }
    // --- End Utility Functions ---


    // Function to show the custom confirmation modal
    function showConfirmationModal(itemId, itemTitle) {
        currentItemIdToDelete = itemId;
        currentItemTitleToDelete = itemTitle;
        modalTitle.textContent = `Delete "${itemTitle}"?`;
        modalMessage.textContent = `Are you sure you want to delete "${itemTitle}" (ID: ${itemId}) from the database? This action is irreversible and will also attempt to remove the associated symlink and update Plex.`;
        confirmationModal.classList.remove('hidden');
        confirmationModal.classList.add('active'); // For potential CSS animations
    }

    // Function to hide the custom confirmation modal
    function hideConfirmationModal() {
        confirmationModal.classList.add('hidden');
        confirmationModal.classList.remove('active');
        currentItemIdToDelete = null;
        currentItemTitleToDelete = null;
    }

    // Function to handle the actual deletion request
    function executeDeletion() {
        if (!currentItemIdToDelete) {
            console.error("No item ID set for deletion.");
            hideConfirmationModal();
            return;
        }

        showLoadingIndicator('Deleting item...');

        fetch(`/api/media_items/${currentItemIdToDelete}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
                // If you have CSRF tokens or other authentication headers, add them here
                // Example: 'X-CSRFToken': getCsrfToken()
            }
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            // If response is not OK, try to parse error message from body
            return response.json().then(errorData => {
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }).catch(() => {
                throw new Error(`HTTP error! Status: ${response.status}`);
            });
        })
        .then(data => {
            // Remove the row from the table on success
            // Find the button that triggered the modal, then its parent row
            const rowToRemove = document.querySelector(`button[data-id="${currentItemIdToDelete}"]`).closest('tr');
            if (rowToRemove) {
                rowToRemove.remove();
            }
            hideConfirmationModal();
            showNotification(data.message || 'Item deleted successfully!', 'success');
        })
        .catch(error => {
            console.error('Error deleting item:', error);
            hideConfirmationModal();
            showNotification(`Failed to delete item: ${error.message}`, 'error');
        })
        .finally(() => {
            hideLoadingIndicator();
        });
    }

    // --- Event Listeners ---

    // Event listener for all individual delete buttons (using event delegation on body)
    document.body.addEventListener('click', function(event) {
        if (event.target.closest('.delete-item-btn')) {
            const button = event.target.closest('.delete-item-btn');
            const itemId = button.dataset.id;
            const itemTitle = button.dataset.title;
            showConfirmationModal(itemId, itemTitle);
        }
    });

    // Event listeners for modal buttons
    cancelDeleteBtn.addEventListener('click', hideConfirmationModal);
    confirmDeleteBtn.addEventListener('click', executeDeletion);

    // Optional: Close modal if clicking outside (but within the overlay)
    confirmationModal.addEventListener('click', function(event) {
        if (event.target === confirmationModal) {
            hideConfirmationModal();
        }
    });

    // --- Batch Deletion (Future Enhancement - UI elements are in HTML but logic is not here yet) ---
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const itemCheckboxes = document.querySelectorAll('.item-checkbox');
    const batchDeleteBtn = document.getElementById('batchDeleteBtn');

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            itemCheckboxes.forEach(checkbox => {
                checkbox.checked = selectAllCheckbox.checked;
            });
            toggleBatchButtons();
        });
    }

    itemCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', toggleBatchButtons);
    });

    function toggleBatchButtons() {
        const anyChecked = Array.from(itemCheckboxes).some(checkbox => checkbox.checked);
        if (anyChecked) {
            batchDeleteBtn.classList.remove('hidden');
        } else {
            batchDeleteBtn.classList.add('hidden');
        }
    }

    // Placeholder for batch delete logic (to be implemented in a later step)
    if (batchDeleteBtn) {
        batchDeleteBtn.addEventListener('click', function() {
            const selectedIds = Array.from(itemCheckboxes)
                                .filter(checkbox => checkbox.checked)
                                .map(checkbox => checkbox.dataset.id);
            if (selectedIds.length > 0) {
                if (confirm(`Are you sure you want to delete ${selectedIds.length} selected items?`)) {
                    // Call a batch delete function here
                    console.log('Batch delete initiated for IDs:', selectedIds);
                    showNotification(`Attempting to delete ${selectedIds.length} items.`, 'info');
                    // You'd send a new fetch request to a /api/media_items/batch_delete endpoint
                    // and then update the UI based on the response.
                }
            } else {
                showNotification('No items selected for batch deletion.', 'warning');
            }
        });
    }

    // --- Filtering and Sorting (Future Enhancement - UI elements are in HTML but logic is not here yet) ---
    const searchInput = document.getElementById('search');
    const filterStateSelect = document.getElementById('filterState');
    const filterTypeSelect = document.getElementById('filterType');
    const sortableHeaders = document.querySelectorAll('.sortable');

    // Function to apply filters and sorting (will reload or update table via AJAX)
    function applyFiltersAndSort() {
        const currentUrl = new URL(window.location.href);
        const params = currentUrl.searchParams;

        // Update search parameter
        if (searchInput) {
            if (searchInput.value) {
                params.set('search', searchInput.value);
            } else {
                params.delete('search');
            }
        }

        // Update state filter parameter
        if (filterStateSelect) {
            if (filterStateSelect.value) {
                params.set('state', filterStateSelect.value);
            } else {
                params.delete('state');
            }
        }

        // Update type filter parameter
        if (filterTypeSelect) {
            if (filterTypeSelect.value) {
                params.set('type', filterTypeSelect.value);
            } else {
                params.delete('type');
            }
        }

        // Update sorting parameters (from current URL or default)
        let sortBy = params.get('sort_by') || 'title'; // Default sort
        let sortOrder = params.get('order') || 'asc'; // Default order

        // Reconstruct URL and navigate or fetch new data
        currentUrl.search = params.toString();
        // For simplicity, we'll just reload the page with new params.
        // For a smoother UX, you'd fetch data via AJAX and update the table dynamically.
        window.location.href = currentUrl.toString();
    }

    // Attach event listeners for filters and search
    if (searchInput) searchInput.addEventListener('input', debounce(applyFiltersAndSort, 500));
    if (filterStateSelect) filterStateSelect.addEventListener('change', applyFiltersAndSort);
    if (filterTypeSelect) filterTypeSelect.addEventListener('change', applyFiltersAndSort);

    // Attach event listeners for sorting headers
    sortableHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const currentSortBy = this.dataset.sort;
            const currentUrl = new URL(window.location.href);
            const params = currentUrl.searchParams;

            let newOrder = 'asc';
            if (params.get('sort_by') === currentSortBy) {
                newOrder = (params.get('order') === 'asc' ? 'desc' : 'asc');
            }

            params.set('sort_by', currentSortBy);
            params.set('order', newOrder);
            params.set('page', '1'); // Reset to first page on sort change

            currentUrl.search = params.toString();
            window.location.href = currentUrl.toString();
        });
    });

    // Debounce function to limit how often a function is called
    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), delay);
        };
    }
});
