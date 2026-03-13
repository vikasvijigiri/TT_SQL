import os
import psycopg2
import requests
import re
import string
from typing import List, Dict, Any, Optional, Tuple
from psycopg2 import pool
from app.models.config import settings

class DatabaseUtil:
    _connection_pool = None

    @classmethod
    def initialize_pool(cls):
        """Initializes the connection pool using environment variables."""
        if cls._connection_pool is None:
            try:
                cls._connection_pool = psycopg2.pool.SimpleConnectionPool(
                    1,
                    10,
                    user=settings.RDS_USER,
                    password=settings.RDS_PASSWORD,
                    host=settings.RDS_HOST,
                    port=settings.RDS_PORT,
                    database=settings.RDS_DATABASE
                )
                print("Connection pool initialized successfully")
            except (Exception, psycopg2.Error) as error:
                print(f"Error while connecting to PostgreSQL: {error}")
                raise

    @classmethod
    def get_connection(cls):
        """Gets a connection from the pool."""
        if cls._connection_pool is None:
            cls.initialize_pool()
        return cls._connection_pool.getconn()

    @classmethod
    def return_connection(cls, connection):
        """Returns a connection to the pool."""
        if cls._connection_pool:
            cls._connection_pool.putconn(connection)

    @classmethod
    def close_all_connections(cls):
        """Closes all connections in the pool."""
        if cls._connection_pool:
            cls._connection_pool.closeall()
            print("Connection pool closed")

    @staticmethod
    def execute_query(query, params=None, fetch=False):
        """
        Executes a SQL query.
        
        Args:
            query (str): The SQL query to execute.
            params (tuple, optional): Parameters for the query. Defaults to None.
            fetch (bool, optional): Whether to fetch results. Defaults to False.
            
        Returns:
            list: The fetched results if fetch is True, otherwise None.
        """
        conn = DatabaseUtil.get_connection()
        cursor = conn.cursor()
        results = None
        try:
            cursor.execute(query, params)
            if fetch:
                results = cursor.fetchall()
            conn.commit()
        except (Exception, psycopg2.Error) as error:
            print(f"Error executing query: {error}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            DatabaseUtil.return_connection(conn)
        return results

def raw_socket_request(url_str, api_key, payload_dict=None, path="", method="GET"):
    """HTTP helper using requests library for robustness."""
    full_url = url_str.rstrip('/') + path
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    try:
        if method == "GET":
            response = requests.get(full_url, headers=headers, timeout=30)
        elif method == "PUT":
            response = requests.put(full_url, headers=headers, json=payload_dict, timeout=30)
        elif method == "DELETE":
            response = requests.delete(full_url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(full_url, headers=headers, json=payload_dict, timeout=30)
        return True, response.json()
    except Exception as e:
        return False, str(e)

