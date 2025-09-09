"""
ICICI Direct API Client
"""

import requests
import json
from datetime import datetime, timedelta
import logging

class ICICIAPIClient:
    def __init__(self, api_key, api_secret, access_token=None):
        """
        Initialize ICICI API client

        Args:
            api_key (str): ICICI API key
            api_secret (str): ICICI API secret
            access_token (str): Access token (optional)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.base_url = "https://api.icicidirect.com"
        self.session = requests.Session()

        # Set up logging
        self.logger = logging.getLogger(__name__)

    def _get_headers(self):
        """Get headers for API requests"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-API-Key': self.api_key
        }
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        return headers

    def authenticate(self, username, password, pin):
        """
        Authenticate and get access token

        Args:
            username (str): ICICI username
            password (str): ICICI password
            pin (str): ICICI PIN

        Returns:
            dict: Authentication response
        """
        try:
            url = f"{self.base_url}/oauth/token"
            payload = {
                'grant_type': 'password',
                'username': username,
                'password': password,
                'pin': pin,
                'client_id': self.api_key,
                'client_secret': self.api_secret
            }

            response = self.session.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()

            data = response.json()
            self.access_token = data.get('access_token')
            return data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Authentication failed: {e}")
            raise

    def refresh_token(self, refresh_token):
        """
        Refresh access token

        Args:
            refresh_token (str): Refresh token

        Returns:
            dict: Token refresh response
        """
        try:
            url = f"{self.base_url}/oauth/token"
            payload = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': self.api_key,
                'client_secret': self.api_secret
            }

            response = self.session.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()

            data = response.json()
            self.access_token = data.get('access_token')
            return data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Token refresh failed: {e}")
            raise

    def get_quote(self, symbol, exchange="NSE"):
        """
        Get quote for a symbol

        Args:
            symbol (str): Trading symbol
            exchange (str): Exchange (NSE, BSE)

        Returns:
            dict: Quote data
        """
        try:
            url = f"{self.base_url}/market/quote"
            params = {
                'symbol': symbol,
                'exchange': exchange
            }

            response = self.session.get(url, params=params, headers=self._get_headers())
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get quote for {symbol}: {e}")
            raise

    def place_order(self, symbol, side, quantity, price=None, order_type="MARKET",
                   product="CNC", exchange="NSE", validity="DAY"):
        """
        Place an order

        Args:
            symbol (str): Trading symbol
            side (str): BUY or SELL
            quantity (int): Quantity
            price (float): Price for limit orders
            order_type (str): MARKET, LIMIT, SL, SL-M
            product (str): CNC, MIS, NRML
            exchange (str): NSE, BSE
            validity (str): DAY, IOC

        Returns:
            dict: Order response
        """
        try:
            url = f"{self.base_url}/orders"
            payload = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'order_type': order_type,
                'product': product,
                'exchange': exchange,
                'validity': validity
            }

            if price and order_type != "MARKET":
                payload['price'] = price

            response = self.session.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to place {side} order for {symbol}: {e}")
            raise

    def get_order_status(self, order_id):
        """
        Get order status

        Args:
            order_id (str): Order ID

        Returns:
            dict: Order status
        """
        try:
            url = f"{self.base_url}/orders/{order_id}"

            response = self.session.get(url, headers=self._get_headers())
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get order status for {order_id}: {e}")
            raise

    def cancel_order(self, order_id):
        """
        Cancel an order

        Args:
            order_id (str): Order ID

        Returns:
            dict: Cancellation response
        """
        try:
            url = f"{self.base_url}/orders/{order_id}"

            response = self.session.delete(url, headers=self._get_headers())
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    def get_portfolio(self):
        """
        Get portfolio holdings

        Returns:
            dict: Portfolio data
        """
        try:
            url = f"{self.base_url}/portfolio"

            response = self.session.get(url, headers=self._get_headers())
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get portfolio: {e}")
            raise

    def get_orders(self):
        """
        Get order history

        Returns:
            dict: Orders data
        """
        try:
            url = f"{self.base_url}/orders"

            response = self.session.get(url, headers=self._get_headers())
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get orders: {e}")
            raise
