const API_BASE = '/api';

// Update slider values in real-time
document.getElementById('fluffiness').addEventListener('input', (e) => {
    document.getElementById('fluffinessValue').textContent = e.target.value;
});

document.getElementById('magical').addEventListener('input', (e) => {
    document.getElementById('magicalValue').textContent = parseFloat(e.target.value).toFixed(1);
});

// Form submission
document.getElementById('pancakeForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = {
        name: document.getElementById('name').value,
        fluffiness_level: parseInt(document.getElementById('fluffiness').value),
        syrup_type: document.getElementById('syrupType').value || null,
        is_buttery: document.getElementById('isButter').checked,
        magical_factor: parseFloat(document.getElementById('magical').value),
        taste_notes: document.getElementById('tasteNotes').value || null
    };

    try {
        const response = await fetch(`${API_BASE}/pancakes`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            throw new Error('Failed to create pancake');
        }

        // Reset form
        document.getElementById('pancakeForm').reset();
        document.getElementById('fluffinessValue').textContent = '5';
        document.getElementById('magicalValue').textContent = '5.0';
        document.getElementById('isButter').checked = true;

        // Reload pancakes
        await loadPancakes();

        // Show success message
        showMessage('✨ Pancake created! How delicious! ✨', 'success');
    } catch (error) {
        console.error('Error:', error);
        showMessage('Oops! Something went wrong. Please try again.', 'error');
    }
});

// Load all pancakes
async function loadPancakes() {
    try {
        const response = await fetch(`${API_BASE}/pancakes`);
        if (!response.ok) {
            throw new Error('Failed to load pancakes');
        }

        const pancakes = await response.json();
        displayPancakes(pancakes);
    } catch (error) {
        console.error('Error loading pancakes:', error);
        document.getElementById('pancakeList').innerHTML = `
            <div class="error">Failed to load pancakes. Please refresh the page.</div>
        `;
    }
}

// Display pancakes
function displayPancakes(pancakes) {
    const pancakeList = document.getElementById('pancakeList');

    if (pancakes.length === 0) {
        pancakeList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-emoji">🥞</div>
                <p>No pancakes yet! Create one to get started.</p>
            </div>
        `;
        return;
    }

    pancakeList.innerHTML = pancakes.map(pancake => `
        <div class="pancake-item">
            <div class="pancake-emoji-item">🥞</div>
            <div class="pancake-name">${escapeHtml(pancake.name)}</div>
            <div class="pancake-field">
                <strong class="pancake-field-label">Fluffiness:</strong> ${pancake.fluffiness_level || 'N/A'}/10
            </div>
            <div class="pancake-field">
                <strong class="pancake-field-label">Syrup:</strong> ${pancake.syrup_type ? getSyrupEmoji(pancake.syrup_type) + ' ' + pancake.syrup_type : 'None'}
            </div>
            <div class="pancake-field">
                <strong class="pancake-field-label">Buttery:</strong> ${pancake.is_buttery ? '🧈 Yes' : 'No'}
            </div>
            <div class="pancake-field">
                <strong class="pancake-field-label">Magical:</strong> ${pancake.magical_factor || 'N/A'} ✨
            </div>
            ${pancake.created_at ? `<div class="pancake-field"><strong class="pancake-field-label">Created:</strong> ${new Date(pancake.created_at).toLocaleDateString()}</div>` : ''}
            ${pancake.taste_notes ? `<div class="pancake-field"><strong class="pancake-field-label">Notes:</strong> <em>${escapeHtml(pancake.taste_notes)}</em></div>` : ''}
        </div>
    `).join('');
}

// Helper function to get syrup emoji
function getSyrupEmoji(syrupType) {
    const emojis = {
        'maple': '🍁',
        'chocolate': '🍫',
        'strawberry': '🍓',
        'caramel': '🍯',
        'blueberry': '🫐',
        'honey': '🍯'
    };
    return emojis[syrupType] || '🍯';
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Show message
function showMessage(message, type) {
    const messageEl = document.createElement('div');
    messageEl.className = type;
    messageEl.textContent = message;
    messageEl.style.position = 'fixed';
    messageEl.style.top = '20px';
    messageEl.style.right = '20px';
    messageEl.style.zIndex = '1000';
    messageEl.style.minWidth = '300px';
    document.body.appendChild(messageEl);

    setTimeout(() => {
        messageEl.remove();
    }, 3000);
}

// Bulk generate random pancakes
async function generateRandomPancakes() {
    const syrups = ['maple', 'chocolate', 'strawberry', 'caramel', 'blueberry', 'honey'];
    const pancakeNames = [
        'Blueberry Bliss', 'Chocolate Dream', 'Strawberry Paradise', 'Golden Stack',
        'Fluffy Cloud', 'Maple Sunrise', 'Caramel Crunch', 'Honey Sweet',
        'Berry Burst', 'Cosmic Pancake', 'Magic Moment', 'Summer Stack',
        'Vanilla Victory', 'Chocolate Chip Delight', 'Rainbow Pancake', 'Midnight Stack',
        'Sunrise Special', 'Crystal Clear', 'Buttery Bliss', 'Sweet Dreams'
    ];
    const tasteDescriptions = [
        'Absolutely delicious!', 'Perfectly fluffy', 'Melts in your mouth', 'Simply heavenly',
        'Best batch yet', 'Cloud-like texture', 'Pure magic', 'Unforgettable', 'Divine',
        'Spectacular', 'Outstanding', 'Phenomenal', 'Exquisite', 'Marvelous'
    ];

    const pancakesToCreate = [];
    for (let i = 0; i < 10; i++) {
        pancakesToCreate.push({
            name: `${pancakeNames[Math.floor(Math.random() * pancakeNames.length)]} #${Date.now()}-${i}`,
            fluffiness_level: Math.floor(Math.random() * 10) + 1,
            syrup_type: syrups[Math.floor(Math.random() * syrups.length)],
            is_buttery: Math.random() > 0.2,
            magical_factor: parseFloat((Math.random() * 10).toFixed(2)),
            taste_notes: tasteDescriptions[Math.floor(Math.random() * tasteDescriptions.length)]
        });
    }

    const btn = document.getElementById('bulkGenerateBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Creating... 0/10';

    let successCount = 0;
    let failureCount = 0;

    for (let i = 0; i < pancakesToCreate.length; i++) {
        try {
            const response = await fetch(`${API_BASE}/pancakes`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(pancakesToCreate[i])
            });

            if (response.ok) {
                successCount++;
            } else {
                failureCount++;
            }
        } catch (error) {
            console.error('Error creating pancake:', error);
            failureCount++;
        }

        btn.textContent = `⏳ Creating... ${successCount + failureCount}/10`;
    }

    btn.disabled = false;
    btn.textContent = originalText;

    // Reload pancakes
    await loadPancakes();

    // Show success message
    showMessage(`✨ Created ${successCount} pancakes! ${failureCount > 0 ? `(${failureCount} failed)` : ''}`, 'success');
}

// Bulk generate button click handler
document.getElementById('bulkGenerateBtn').addEventListener('click', generateRandomPancakes);

// Load pancakes on page load
loadPancakes();

// Auto-refresh every 10 seconds (optional)
// setInterval(loadPancakes, 10000);
