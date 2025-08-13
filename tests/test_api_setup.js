// Test script to check API setup status
const API_BASE_URL = 'http://localhost:8000/api/v1';

async function testAPISetup() {
    console.log('🔍 Testing API Setup Status...');
    
    // Get the stored token
    const token = localStorage.getItem('access_token');
    if (!token) {
        console.error('❌ No access token found. Please login first.');
        return;
    }
    
    console.log('✅ Access token found');
    
    try {
        // Check API setup status
        const response = await fetch(`${API_BASE_URL}/auth/check-api-setup`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('📊 API Setup Status:', data);
            
            if (data.api_credentials_set) {
                console.log('✅ API credentials are set up');
                
                // Get dashboard data to see broker status
                const dashboardResponse = await fetch(`${API_BASE_URL}/dashboard/dashboard`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                
                if (dashboardResponse.ok) {
                    const dashboardData = await dashboardResponse.json();
                    console.log('📊 Dashboard Data:', {
                        broker: dashboardData.broker,
                        session_id: dashboardData.session_id ? 'Present' : 'None',
                        unused_funds: dashboardData.unused_funds,
                        holdings_count: dashboardData.holdings?.length || 0
                    });
                    
                    if (!dashboardData.broker || dashboardData.broker === 'null') {
                        console.log('⚠️ Broker not connected - should show Zerodha activation');
                    } else {
                        console.log('✅ Broker connected:', dashboardData.broker);
                    }
                }
            } else {
                console.log('❌ API credentials not set up');
            }
        } else {
            console.error('❌ Failed to check API setup:', response.status);
        }
    } catch (error) {
        console.error('❌ Error:', error);
    }
}

// Run the test
testAPISetup();
