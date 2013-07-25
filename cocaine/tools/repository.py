import subprocess
import os

__author__ = 'EvgenySafronov <division494@gmail.com>'


class RepositoryDownloadError(Exception):
    pass


class RepositoryDownloader(object):
    def download(self, url, destination):
        raise NotImplementedError


class GitRepositoryDownloader(RepositoryDownloader):
    def __init__(self, stream=None):
        self.stream = stream or open(os.devnull, 'w')

    def download(self, url, destination):
        devnull = open(os.devnull, 'w')
        process = subprocess.Popen(['git', 'clone', url, destination],
                                   stdout=self.stream,
                                   stderr=self.stream)
        process.wait()
        if process.returncode != 0:
            raise RepositoryDownloadError('Cannot download repository from "{0}"'.format(url))
