try:
    from core.trading_executor import MultiTimeframeTradingExecutor
    print("Import Successful")
    executor = MultiTimeframeTradingExecutor()
    print("Instantiation Successful")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
