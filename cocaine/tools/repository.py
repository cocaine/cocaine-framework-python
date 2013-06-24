import subprocess
import os

__author__ = 'EvgenySafronov <division494@gmail.com>'


class RepositoryDownloadError(Exception):
    pass


class RepositoryDownloader(object):
    def download(self, url, destination):
        raise NotImplementedError


class GitRepositoryDownloader(RepositoryDownloader):
    def download(self, url, destination):
        devnull = open(os.devnull, 'w')
        process = subprocess.Popen(['git', 'clone', url, destination],
                                   stdout=devnull,
                                   stderr=devnull)
        process.wait()
        if process.returncode != 0:
            raise RepositoryDownloadError('Cannot download repository from "{0}"'.format(url))
