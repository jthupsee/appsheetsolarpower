document.addEventListener('DOMContentLoaded', () => {
    const locationGrid = document.getElementById('locationGrid');
    const lastUpdatedSpan = document.getElementById('lastUpdated');
    const refreshButton = document.getElementById('refreshButton');

    function updateLastUpdated() {
        const now = new Date();
        lastUpdatedSpan.textContent = now.toLocaleString();
    }

    function getStatusColor(status) {
        switch(status.toLowerCase()) {
            case 'optimal':
                return 'bg-green-500';
            case 'normal':
                return 'bg-yellow-500';
            case 'low':
                return 'bg-red-500';
            default:
                return 'bg-gray-500';
        }
    }

    function createLocationCard(location) {
        const card = document.createElement('div');
        card.className = 'bg-gray-800 rounded-lg shadow-lg p-6';
        
        const statusClass = getStatusColor(location.status);
        
        card.innerHTML = `
            <h2 class="text-xl font-bold mb-4">${location.name}</h2>
            <div class="flex items-center justify-center mb-4">
                <div class="w-4 h-4 rounded-full ${statusClass} mr-2"></div>
                <span class="capitalize">${location.status}</span>
            </div>
            <div class="space-y-2">
                <p>Cloud Cover: ${location.cloud_cover}%</p>
                <p>Power Output: ${location.power_output.toFixed(2)} kW</p>
            </div>
        `;
        
        return card;
    }

    async function fetchSolarData() {
        try {
            const response = await fetch('/api/solar-data');
            if (!response.ok) {
                throw new Error('Failed to fetch solar data');
            }
            const data = await response.json();
            
            // Clear existing cards
            locationGrid.innerHTML = '';
            
            // Create and append new cards
            Object.entries(data).forEach(([name, locationData]) => {
                const card = createLocationCard({
                    name,
                    status: locationData.status,
                    cloud_cover: locationData.cloud_cover,
                    power_output: locationData.power_output_on_ground
                });
                locationGrid.appendChild(card);
            });
            
            updateLastUpdated();
        } catch (error) {
            console.error('Error fetching solar data:', error);
            locationGrid.innerHTML = `
                <div class="col-span-full text-center text-red-500">
                    Failed to load solar power data. Please try again later.
                </div>
            `;
        }
    }

    // Initial fetch
    fetchSolarData();


    // Manual refresh button
    refreshButton.addEventListener('click', fetchSolarData);
});