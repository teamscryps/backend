# Frontend Integration Guide - Updated Authentication Workflow

## New User Registration Flow

### 1. User Registration (Updated)
```javascript
// POST /api/v1/auth/register
const registerUser = async (email, mobile) => {
  const response = await fetch('/api/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      email: email,
      mobile: mobile 
    })
  });
  
  if (response.ok) {
    // User receives email with generated password
    // Name is automatically extracted from email
    return { success: true, message: 'Registration successful. Please check your email for login credentials.' };
  } else {
    const error = await response.json();
    throw new Error(error.detail);
  }
};
```

### 2. User Login
```javascript
// POST /api/v1/auth/signin
const loginUser = async (email, password) => {
  const formData = new FormData();
  formData.append('username', email);
  formData.append('password', password);
  
  const response = await fetch('/api/v1/auth/signin', {
    method: 'POST',
    body: formData
  });
  
  const { access_token, refresh_token } = await response.json();
  localStorage.setItem('access_token', access_token);
  localStorage.setItem('refresh_token', refresh_token);
};
```

### 3. Get User Profile
```javascript
// GET /api/v1/auth/profile
const getUserProfile = async () => {
  const response = await fetch('/api/v1/auth/profile', {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
  });
  
  if (response.ok) {
    const profile = await response.json();
    return profile;
  } else {
    throw new Error('Failed to get profile');
  }
};
```

### 4. Update User Name
```javascript
// PUT /api/v1/auth/update-name
const updateUserName = async (name) => {
  const response = await fetch('/api/v1/auth/update-name', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`
    },
    body: JSON.stringify({ name })
  });
  
  if (response.ok) {
    const result = await response.json();
    return result;
  } else {
    const error = await response.json();
    throw new Error(error.detail);
  }
};
```

### 5. Check API Setup Status
```javascript
// GET /api/v1/auth/check-api-setup
const checkAPISetup = async () => {
  const response = await fetch('/api/v1/auth/check-api-setup', {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
  });
  const { api_credentials_set } = await response.json();
  return api_credentials_set;
};
```

### 6. First-Time API Setup (if needed)
```javascript
// POST /api/v1/auth/first-time-api-setup
const setupAPICredentials = async (apiData) => {
  const response = await fetch('/api/v1/auth/first-time-api-setup', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`
    },
    body: JSON.stringify(apiData)
  });
};
```

### 7. Update API Credentials
```javascript
// POST /api/v1/auth/update-api-credentials
const updateAPICredentials = async (apiData) => {
  const response = await fetch('/api/v1/auth/update-api-credentials', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`
    },
    body: JSON.stringify(apiData)
  });
  
  if (response.ok) {
    const result = await response.json();
    return result;
  } else {
    const error = await response.json();
    throw new Error(error.detail);
  }
};
```

### 8. Get API Credentials Info
```javascript
// GET /api/v1/auth/api-credentials-info
const getAPICredentialsInfo = async () => {
  const response = await fetch('/api/v1/auth/api-credentials-info', {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
  });
  
  if (response.ok) {
    const info = await response.json();
    return info;
  } else {
    throw new Error('Failed to get API credentials info');
  }
};
```

## Registration Form Implementation

```javascript
// Registration form with mobile number requirement
const createRegistrationForm = () => {
  const form = `
    <div class="registration-form">
      <h2>Create Account</h2>
      <form id="registration-form">
        <div class="form-group">
          <label for="email">Email Address *</label>
          <input type="email" id="email" name="email" required 
                 placeholder="Enter your email address" />
          <small>Your name will be automatically extracted from your email</small>
        </div>
        
        <div class="form-group">
          <label for="mobile">Mobile Number *</label>
          <input type="tel" id="mobile" name="mobile" required 
                 placeholder="Enter your mobile number" 
                 pattern="[0-9]{10,}" />
          <small>Minimum 10 digits required</small>
        </div>
        
        <button type="submit">Create Account</button>
        
        <div class="form-footer">
          <p>By registering, you agree to receive login credentials via email</p>
          <p>Already have an account? <a href="#" onclick="showLoginForm()">Login here</a></p>
        </div>
      </form>
    </div>
  `;
  
  return form;
};

// Handle registration form submission
const handleRegistration = async (e) => {
  e.preventDefault();
  const formData = new FormData(e.target);
  
  const email = formData.get('email');
  const mobile = formData.get('mobile');
  
  // Basic validation
  if (!email || !mobile) {
    alert('Please fill in all required fields');
    return;
  }
  
  if (mobile.length < 10) {
    alert('Mobile number must be at least 10 digits');
    return;
  }
  
  try {
    const result = await registerUser(email, mobile);
    alert(result.message);
    // Show login form after successful registration
    showLoginForm();
  } catch (error) {
    alert('Registration failed: ' + error.message);
  }
};
```

## Profile Management

```javascript
// Profile display and management
const showUserProfile = async () => {
  try {
    const profile = await getUserProfile();
    
    const profileHTML = `
      <div class="user-profile">
        <h2>User Profile</h2>
        <div class="profile-info">
          <div class="info-group">
            <label>Name:</label>
            <span id="user-name">${profile.name}</span>
            <button onclick="showUpdateNameForm()">Edit</button>
          </div>
          
          <div class="info-group">
            <label>Email:</label>
            <span>${profile.email}</span>
          </div>
          
          <div class="info-group">
            <label>Mobile:</label>
            <span>${profile.mobile}</span>
          </div>
          
          <div class="info-group">
            <label>Account Created:</label>
            <span>${new Date(profile.created_at).toLocaleDateString()}</span>
          </div>
          
          <div class="info-group">
            <label>API Setup:</label>
            <span>${profile.api_credentials_set ? 'Completed' : 'Pending'}</span>
          </div>
        </div>
        
        <div class="profile-actions">
          <button onclick="showChangePasswordModal()">Change Password</button>
          <button onclick="showAPISetupModal()" 
                  ${profile.api_credentials_set ? 'disabled' : ''}>
            ${profile.api_credentials_set ? 'API Already Set' : 'Setup API Credentials'}
          </button>
        </div>
      </div>
    `;
    
    document.getElementById('profile-container').innerHTML = profileHTML;
  } catch (error) {
    console.error('Failed to load profile:', error);
  }
};

// Update name form
const showUpdateNameForm = () => {
  const updateForm = `
    <div class="update-name-modal">
      <h3>Update Name</h3>
      <form id="update-name-form">
        <div class="form-group">
          <label for="new-name">New Name</label>
          <input type="text" id="new-name" name="name" required 
                 placeholder="Enter your full name" minlength="2" />
          <small>Minimum 2 characters required</small>
        </div>
        
        <div class="form-actions">
          <button type="submit">Update Name</button>
          <button type="button" onclick="closeUpdateNameModal()">Cancel</button>
        </div>
      </form>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', updateForm);
  
  // Handle form submission
  document.getElementById('update-name-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const newName = formData.get('name').trim();
    
    if (newName.length < 2) {
      alert('Name must be at least 2 characters long');
      return;
    }
    
    try {
      const result = await updateUserName(newName);
      alert('Name updated successfully!');
      closeUpdateNameModal();
      // Refresh profile display
      showUserProfile();
    } catch (error) {
      alert('Failed to update name: ' + error.message);
    }
  });
};

const closeUpdateNameModal = () => {
  const modal = document.querySelector('.update-name-modal');
  if (modal) {
    modal.remove();
  }
};
```

## Name Extraction Examples

The system automatically extracts names from email addresses:

```javascript
// Examples of name extraction
const nameExamples = {
  'john.doe@example.com': 'John Doe',
  'jane_smith@example.com': 'Jane Smith', 
  'user-name@example.com': 'User Name',
  'test.user@domain.com': 'Test User',
  'simple@email.com': 'Simple'
};

// You can show this to users during registration
const showNamePreview = (email) => {
  if (email && email.includes('@')) {
    const namePart = email.split('@')[0];
    const extractedName = namePart
      .replace(/[._-]/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
    
    document.getElementById('name-preview').textContent = 
      `Your name will be: ${extractedName}`;
  }
};
```

## Password Management

### 7. Change Password (Logged in user)
```javascript
// POST /api/v1/auth/change-password
const changePassword = async (oldPassword, newPassword) => {
  const response = await fetch('/api/v1/auth/change-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`
    },
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword
    })
  });
  return response.json();
};
```

### 8. Forgot Password (Step 1: Request OTP)
```javascript
// POST /api/v1/auth/forgot-password
const forgotPassword = async (email) => {
  const response = await fetch('/api/v1/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });
  return response.json();
};
```

### 9. Reset Password (Step 2: Enter OTP and New Password)
```javascript
// POST /api/v1/auth/reset-password
const resetPassword = async (email, otp, newPassword) => {
  const response = await fetch('/api/v1/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: email,
      otp: otp,
      new_password: newPassword
    })
  });
  return response.json();
};
```

## OTP Authentication

### 10. Request OTP
```javascript
// POST /api/v1/auth/request-otp
const requestOTP = async (email) => {
  const response = await fetch('/api/v1/auth/request-otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });
  return response.json();
};
```

### 11. OTP Login
```javascript
// POST /api/v1/auth/otp-login
const loginWithOTP = async (email, otp) => {
  const response = await fetch('/api/v1/auth/otp-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, otp })
  });
  
  const { access_token, refresh_token } = await response.json();
  localStorage.setItem('access_token', access_token);
  localStorage.setItem('refresh_token', refresh_token);
};
```

## Complete Workflow Implementation

```javascript
// Main authentication flow
const handleUserFlow = async () => {
  // Step 1: Check if user is logged in
  const token = localStorage.getItem('access_token');
  if (!token) {
    // Show registration/login form
    return;
  }
  
  // Step 2: Load user profile
  try {
    const profile = await getUserProfile();
    console.log('User profile loaded:', profile);
    
    // Step 3: Check if API credentials are set
    const apiSetup = await checkAPISetup();
    
    if (!apiSetup) {
      // Show first-time API setup modal/popup
      showAPISetupModal();
    } else {
      // User is fully set up - redirect to dashboard
      window.location.href = '/dashboard';
    }
  } catch (error) {
    console.error('Failed to load user data:', error);
    // Token might be expired, redirect to login
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    showLoginForm();
  }
};

// API Setup Modal
const showAPISetupModal = () => {
  const modal = `
    <div class="api-setup-modal">
      <h2>Welcome! Please set up your trading account</h2>
      <form id="api-setup-form">
        <div class="form-group">
          <label for="broker">Broker *</label>
          <select name="broker" required>
            <option value="">Select Broker</option>
            <option value="zerodha">Zerodha</option>
            <option value="groww">Groww</option>
            <option value="upstox">Upstox</option>
          </select>
        </div>
        
        <div class="form-group">
          <label for="api_key">API Key *</label>
          <input type="text" name="api_key" placeholder="API Key" required />
        </div>
        
        <div class="form-group">
          <label for="api_secret">API Secret *</label>
          <input type="password" name="api_secret" placeholder="API Secret" required />
        </div>
        
        <!-- Zerodha specific -->
        <div id="zerodha-fields" style="display: none;">
          <div class="form-group">
            <label for="request_token">Request Token</label>
            <input type="text" name="request_token" placeholder="Request Token" />
          </div>
        </div>
        
        <!-- Groww specific -->
        <div id="groww-fields" style="display: none;">
          <div class="form-group">
            <label for="totp_secret">TOTP Secret</label>
            <input type="text" name="totp_secret" placeholder="TOTP Secret" />
          </div>
        </div>
        
        <!-- Upstox specific -->
        <div id="upstox-fields" style="display: none;">
          <div class="form-group">
            <label for="auth_code">Authorization Code</label>
            <input type="text" name="auth_code" placeholder="Authorization Code" />
          </div>
        </div>
        
        <button type="submit">Set Up Account</button>
      </form>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', modal);
  
  // Handle broker selection to show/hide specific fields
  document.querySelector('select[name="broker"]').addEventListener('change', (e) => {
    const broker = e.target.value;
    
    // Hide all broker-specific fields
    document.getElementById('zerodha-fields').style.display = 'none';
    document.getElementById('groww-fields').style.display = 'none';
    document.getElementById('upstox-fields').style.display = 'none';
    
    // Show relevant fields based on broker
    if (broker === 'zerodha') {
      document.getElementById('zerodha-fields').style.display = 'block';
    } else if (broker === 'groww') {
      document.getElementById('groww-fields').style.display = 'block';
    } else if (broker === 'upstox') {
      document.getElementById('upstox-fields').style.display = 'block';
    }
  });
  
  // Handle form submission
  document.getElementById('api-setup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    const apiData = {
      broker: formData.get('broker'),
      api_key: formData.get('api_key'),
      api_secret: formData.get('api_secret'),
      request_token: formData.get('request_token') || null,
      totp_secret: formData.get('totp_secret') || null,
      auth_code: formData.get('auth_code') || null
    };
    
    try {
      await setupAPICredentials(apiData);
      // Remove modal and redirect to dashboard
      document.querySelector('.api-setup-modal').remove();
      window.location.href = '/dashboard';
    } catch (error) {
      console.error('API setup failed:', error);
      alert('Failed to set up API credentials: ' + error.message);
    }
  });
};

// Password Change Modal
const showChangePasswordModal = () => {
  const modal = `
    <div class="change-password-modal">
      <h2>Change Password</h2>
      <form id="change-password-form">
        <input type="password" name="old_password" placeholder="Current Password" required />
        <input type="password" name="new_password" placeholder="New Password" required />
        <input type="password" name="confirm_password" placeholder="Confirm New Password" required />
        <button type="submit">Change Password</button>
      </form>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', modal);
  
  // Handle form submission
  document.getElementById('change-password-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    const oldPassword = formData.get('old_password');
    const newPassword = formData.get('new_password');
    const confirmPassword = formData.get('confirm_password');
    
    if (newPassword !== confirmPassword) {
      alert('New passwords do not match!');
      return;
    }
    
    try {
      await changePassword(oldPassword, newPassword);
      alert('Password changed successfully!');
      document.querySelector('.change-password-modal').remove();
    } catch (error) {
      alert('Failed to change password: ' + error.message);
    }
  });
};

// Forgot Password Modal
const showForgotPasswordModal = () => {
  const modal = `
    <div class="forgot-password-modal">
      <h2>Forgot Password</h2>
      <form id="forgot-password-form">
        <input type="email" name="email" placeholder="Enter your email" required />
        <button type="submit">Send Reset OTP</button>
      </form>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', modal);
  
  // Handle form submission
  document.getElementById('forgot-password-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const email = formData.get('email');
    
    try {
      await forgotPassword(email);
      alert('OTP sent to your email!');
      // Show reset password form
      showResetPasswordForm(email);
    } catch (error) {
      alert('Failed to send OTP: ' + error.message);
    }
  });
};

// Reset Password Form
const showResetPasswordForm = (email) => {
  const resetForm = `
    <div class="reset-password-form">
      <h2>Reset Password</h2>
      <form id="reset-password-form">
        <input type="text" name="otp" placeholder="Enter OTP from email" required />
        <input type="password" name="new_password" placeholder="New Password" required />
        <input type="password" name="confirm_password" placeholder="Confirm New Password" required />
        <button type="submit">Reset Password</button>
      </form>
    </div>
  `;
  
  // Replace forgot password form with reset form
  document.querySelector('.forgot-password-modal').innerHTML = resetForm;
  
  // Handle reset form submission
  document.getElementById('reset-password-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    const otp = formData.get('otp');
    const newPassword = formData.get('new_password');
    const confirmPassword = formData.get('confirm_password');
    
    if (newPassword !== confirmPassword) {
      alert('Passwords do not match!');
      return;
    }
    
    try {
      await resetPassword(email, otp, newPassword);
      alert('Password reset successfully!');
      document.querySelector('.forgot-password-modal').remove();
    } catch (error) {
      alert('Failed to reset password: ' + error.message);
    }
  });
};
```

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/register` | POST | Register user with email & mobile (generates password) |
| `/api/v1/auth/signin` | POST | Login with email/password |
| `/api/v1/auth/profile` | GET | Get user profile information |
| `/api/v1/auth/update-name` | PUT | Update user's name |
| `/api/v1/auth/change-password` | POST | Change password (requires old password) |
| `/api/v1/auth/forgot-password` | POST | Request password reset OTP |
| `/api/v1/auth/reset-password` | POST | Reset password using OTP |
| `/api/v1/auth/request-otp` | POST | Request OTP for login |
| `/api/v1/auth/otp-login` | POST | Login using OTP |
| `/api/v1/auth/check-api-setup` | GET | Check if API credentials set |
| `/api/v1/auth/first-time-api-setup` | POST | Set up API credentials first time |
| `/api/v1/auth/update-api-credentials` | POST | Update existing API credentials |
| `/api/v1/auth/api-credentials-info` | GET | Get information about API credentials |
| `/api/v1/auth/refresh` | POST | Refresh access token |
| `/api/v1/auth/logout` | POST | Logout user |

## User Journey

### New User Registration:
1. **Register**: User enters email & mobile → System generates password → Email sent with credentials
2. **Name Extraction**: System automatically extracts name from email address
3. **Login**: User enters email + generated password → Gets access token
4. **Profile View**: User can view and update their profile information
5. **First Login Check**: System checks if API credentials are set
6. **API Setup** (if needed): User enters broker credentials → Stored encrypted
7. **Dashboard Access**: User can now access full dashboard functionality

### Profile Management:
1. **View Profile**: User can see their name, email, mobile, and account status
2. **Update Name**: User can change their name (minimum 2 characters)
3. **Change Password**: User enters old password + new password → Password updated
4. **Forgot Password**: User enters email → OTP sent → User enters OTP + new password → Password reset

### API Credentials Management:
1. **View Current Setup**: User can see their current broker, API status, and last update time
2. **Update Credentials**: User can change their API key, secret, and broker-specific tokens
3. **First-Time Setup**: New users can set up their initial API credentials
4. **Broker-Specific Fields**: Different brokers show relevant additional fields (Zerodha, Groww, Upstox)

## Security Features

- **Mobile Number Required**: All new registrations require mobile number
- **Name Extraction**: Names automatically extracted from email addresses
- **Password Generation**: Passwords are generated securely and sent via email
- **API Credentials Encryption**: API credentials are encrypted before storage
- **Session Management**: Session tokens are managed automatically
- **Rate Limiting**: Prevents abuse of registration and OTP endpoints
- **Data Encryption**: All sensitive data is encrypted in database
- **OTP System**: OTP-based password reset with configurable expiry
- **Old Password Verification**: Required for password changes
- **Token-based Authentication**: JWT tokens for secure API access 

## API Credentials Management

```javascript
// API Credentials Management UI
const showAPICredentialsManager = async () => {
  try {
    const credentialsInfo = await getAPICredentialsInfo();
    
    const managerHTML = `
      <div class="api-credentials-manager">
        <h2>API Credentials Management</h2>
        
        <div class="current-credentials">
          <h3>Current Setup</h3>
          <div class="credentials-info">
            <div class="info-group">
              <label>Broker:</label>
              <span>${credentialsInfo.broker}</span>
            </div>
            
            <div class="info-group">
              <label>API Key:</label>
              <span>${credentialsInfo.has_api_key ? '✓ Set' : '✗ Not Set'}</span>
            </div>
            
            <div class="info-group">
              <label>API Secret:</label>
              <span>${credentialsInfo.has_api_secret ? '✓ Set' : '✗ Not Set'}</span>
            </div>
            
            <div class="info-group">
              <label>Broker Token:</label>
              <span>${credentialsInfo.has_broker_token ? '✓ Set' : '✗ Not Set'}</span>
            </div>
            
            <div class="info-group">
              <label>Last Updated:</label>
              <span>${new Date(credentialsInfo.session_updated_at).toLocaleString()}</span>
            </div>
          </div>
        </div>
        
        <div class="update-credentials">
          <h3>Update Credentials</h3>
          <button onclick="showUpdateAPICredentialsForm()" class="update-btn">
            Update API Credentials
          </button>
        </div>
      </div>
    `;
    
    document.getElementById('api-credentials-container').innerHTML = managerHTML;
  } catch (error) {
    console.error('Failed to load API credentials info:', error);
    // Show setup form if credentials not set
    showAPISetupModal();
  }
};

// Update API Credentials Form
const showUpdateAPICredentialsForm = () => {
  const updateForm = `
    <div class="update-api-credentials-modal">
      <h3>Update API Credentials</h3>
      <form id="update-api-credentials-form">
        <div class="form-group">
          <label for="broker">Broker *</label>
          <select name="broker" required>
            <option value="">Select Broker</option>
            <option value="zerodha">Zerodha</option>
            <option value="groww">Groww</option>
            <option value="upstox">Upstox</option>
          </select>
        </div>
        
        <div class="form-group">
          <label for="api_key">API Key *</label>
          <input type="text" name="api_key" placeholder="Enter API Key" required />
        </div>
        
        <div class="form-group">
          <label for="api_secret">API Secret *</label>
          <input type="password" name="api_secret" placeholder="Enter API Secret" required />
        </div>
        
        <!-- Zerodha specific -->
        <div id="zerodha-update-fields" style="display: none;">
          <div class="form-group">
            <label for="request_token">Request Token</label>
            <input type="text" name="request_token" placeholder="Enter Request Token" />
          </div>
        </div>
        
        <!-- Groww specific -->
        <div id="groww-update-fields" style="display: none;">
          <div class="form-group">
            <label for="totp_secret">TOTP Secret</label>
            <input type="text" name="totp_secret" placeholder="Enter TOTP Secret" />
          </div>
        </div>
        
        <!-- Upstox specific -->
        <div id="upstox-update-fields" style="display: none;">
          <div class="form-group">
            <label for="auth_code">Authorization Code</label>
            <input type="text" name="auth_code" placeholder="Enter Authorization Code" />
          </div>
        </div>
        
        <div class="form-actions">
          <button type="submit">Update Credentials</button>
          <button type="button" onclick="closeUpdateAPICredentialsModal()">Cancel</button>
        </div>
      </form>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', updateForm);
  
  // Handle broker selection to show/hide specific fields
  document.querySelector('select[name="broker"]').addEventListener('change', (e) => {
    const broker = e.target.value;
    
    // Hide all broker-specific fields
    document.getElementById('zerodha-update-fields').style.display = 'none';
    document.getElementById('groww-update-fields').style.display = 'none';
    document.getElementById('upstox-update-fields').style.display = 'none';
    
    // Show relevant fields based on broker
    if (broker === 'zerodha') {
      document.getElementById('zerodha-update-fields').style.display = 'block';
    } else if (broker === 'groww') {
      document.getElementById('groww-update-fields').style.display = 'block';
    } else if (broker === 'upstox') {
      document.getElementById('upstox-update-fields').style.display = 'block';
    }
  });
  
  // Handle form submission
  document.getElementById('update-api-credentials-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    const apiData = {
      broker: formData.get('broker'),
      api_key: formData.get('api_key'),
      api_secret: formData.get('api_secret'),
      request_token: formData.get('request_token') || null,
      totp_secret: formData.get('totp_secret') || null,
      auth_code: formData.get('auth_code') || null
    };
    
    try {
      const result = await updateAPICredentials(apiData);
      alert('API credentials updated successfully!');
      closeUpdateAPICredentialsModal();
      // Refresh the credentials manager
      showAPICredentialsManager();
    } catch (error) {
      alert('Failed to update API credentials: ' + error.message);
    }
  });
};

const closeUpdateAPICredentialsModal = () => {
  const modal = document.querySelector('.update-api-credentials-modal');
  if (modal) {
    modal.remove();
  }
};
``` 