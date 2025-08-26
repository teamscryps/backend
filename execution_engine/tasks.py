try:
    from celery import Celery  # type: ignore
except ImportError:  # allow running tests without celery installed
    Celery = None  # type: ignore

from execution_engine.executor import execute_bulk_trade

if Celery is not None:
    celery_app = Celery('execution_engine', broker='redis://localhost:6379/0')
    register_task = celery_app.task
else:
    class _Dummy:
        def task(self, *_, **__):
            def wrap(fn):
                return fn
            return wrap
    celery_app = _Dummy()
    register_task = celery_app.task

@register_task
def bulk_trade_execution(broker_type, stock_symbol, percent_quantity, user_ids):
    return execute_bulk_trade(broker_type, stock_symbol, percent_quantity, user_ids)