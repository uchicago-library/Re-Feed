document.addEventListener('DOMContentLoaded', function() {
    // Tag entries
    const tagForms = document.querySelectorAll('form[action^="/tag_entry/"]');
    tagForms.forEach(form => {
        form.addEventListener('submit', function(event) {
            event.preventDefault();

            const formData = new FormData(form);
            const actionUrl = form.action;

            fetch(actionUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                }
                throw new Error('Network response was not OK.');
            })
            .then(tagId => {
                // Create a new tag element and append it to the DOM
                const newTagItem = document.createElement('li');
                const tagName = formData.get('tags');
                const entryId = form.action.split('/').pop();
                newTagItem.innerHTML = `
                    <span class="tag-name tag-name-${tagName.toLowerCase()}">${tagName}</span>
                    <form action="/delete_tag/${entryId}/${tagId}" method="post">
                        <input type="hidden" name="_method" value="DELETE">
                        <button type="submit" class="delete delete-${tagName.toLowerCase()}">Delete Tag</button>
                    </form>
                `;
                // Append the new tag item to the end of the entry
                let entryItemParent = form.closest('li');
                let entryItem = entryItemParent.querySelector('.current-tags');
                if (entryItem == null) {
                    entryItem = document.createElement('ul');
                    entryItem.classList.add('current-tags');
                    entryItemParent.appendChild(entryItem);
                }
                entryItem.appendChild(newTagItem);
                form.reset();
            })
            .catch(error => {
                console.error('There was a problem with the fetch operation:', error);
            });
        });
    });

    // Delete tags
    document.addEventListener('submit', function(event) {
        if (event.target.matches('form[action^="/delete_tag/"]')) {
            event.preventDefault();

            const actionUrl = event.target.action;
            const formData = new FormData(event.target);

            fetch(actionUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(() => {
                // Remove the tag from the DOM
                const tagItem = event.target.parentElement;
                tagItem.remove();
            })
            .catch(error => {
                console.error('There was a problem with the fetch operation:', error);
            });
        }
    });
});
