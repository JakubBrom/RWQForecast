import time

def measure_execution_time(func):
    """
    Decorator function to measure the execution time of the input function.

    :param func: The function to measure the execution time of.
    :return wrapper: The wrapper function that measures the execution time of the input function.
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Function {func.__name__} took {execution_time:.4f} seconds to execute")
        return result

    return wrapper