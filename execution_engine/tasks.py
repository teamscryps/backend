from celery import Celery
from execution_engine.executor import execute_bulk_trade

celery_app = Celery('execution_engine', broker='redis://localhost:6379/0')

@celery_app.task
def bulk_trade_execution(broker_type, stock_symbol, percent_quantity, user_ids):
    return execute_bulk_trade(broker_type, stock_symbol, percent_quantity, user_ids) 