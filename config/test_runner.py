import multiprocessing

from django.test.runner import DiscoverRunner


class ParallelTestRunner(DiscoverRunner):
    """--parallel 없이도 자동으로 CPU 코어 수만큼 병렬 실행."""

    def __init__(self, **kwargs):
        if kwargs.get('parallel', 0) == 0:
            kwargs['parallel'] = multiprocessing.cpu_count()
        super().__init__(**kwargs)
