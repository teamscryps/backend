// React Hook for API Integration
import { useState, useEffect } from 'react';
import * as api from './frontend-api-service.js';

export const useAuth = () => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const currentUser = api.getCurrentUser();
        setUser(currentUser);
        setLoading(false);
    }, []);

    const login = async (email, password) => {
        try {
            setLoading(true);
            const userData = await api.signin(email, password);
            setUser(api.getCurrentUser());
            return userData;
        } catch (error) {
            throw error;
        } finally {
            setLoading(false);
        }
    };

    const signup = async (email, password) => {
        try {
            setLoading(true);
            const userData = await api.signup(email, password);
            setUser(api.getCurrentUser());
            return userData;
        } catch (error) {
            throw error;
        } finally {
            setLoading(false);
        }
    };

    const logout = async () => {
        try {
            await api.logout();
            setUser(null);
        } catch (error) {
            console.error('Logout error:', error);
        }
    };

    const requestOTP = async (email) => {
        return await api.requestOTP(email);
    };

    const otpLogin = async (email, otp) => {
        try {
            setLoading(true);
            const userData = await api.otpLogin(email, otp);
            setUser(api.getCurrentUser());
            return userData;
        } catch (error) {
            throw error;
        } finally {
            setLoading(false);
        }
    };

    return {
        user,
        loading,
        isAuthenticated: api.isAuthenticated(),
        login,
        signup,
        logout,
        requestOTP,
        otpLogin
    };
};

export const useDashboard = () => {
    const [dashboardData, setDashboardData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchDashboardData = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await api.getDashboardData();
            setDashboardData(data);
            return data;
        } catch (error) {
            setError(error.message);
            throw error;
        } finally {
            setLoading(false);
        }
    };

    const activateBrokerage = async (brokerageData) => {
        try {
            setLoading(true);
            setError(null);
            const result = await api.activateBrokerage(brokerageData);
            return result;
        } catch (error) {
            setError(error.message);
            throw error;
        } finally {
            setLoading(false);
        }
    };

    return {
        dashboardData,
        loading,
        error,
        fetchDashboardData,
        activateBrokerage
    };
}; 