import os
import shutil
import tarfile
import tempfile
from cocaine.futures.chain import Chain
from cocaine.tools.tools import StorageAction, ToolsError, AppUploadAction
import logging

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class AppLocalUploadAction(StorageAction):
    def __init__(self, storage, **config):
        super(AppLocalUploadAction, self).__init__(storage, **config)
        self.path = config.get('path', '.')
        self.name = config.get('name')
        self._log = logging.getLogger(self.__module__ + '.' + self.__class__.__name__)

    def execute(self):
        return Chain().then(self._doMagic)

    def _doMagic(self):
        if self.name is None:
            self.name = os.path.basename(os.path.abspath(self.path))

        if not self.name:
            raise ToolsError('Application has not valid name: "{0}"'.format(self.name))

        # Locate manifests. Priority:
        # root+json     - 111
        # root          - 101
        # other+json    - 11
        # other         - 1
        manifests = []
        for root, dirNames, fileNames in os.walk(self.path):
            for fileName in fileNames:
                if fileName.startswith('manifest'):
                    priority = 1
                    if root == self.path:
                        priority += 100
                    if fileName == 'manifest.json':
                        priority += 10
                    manifests.append((os.path.join(root, fileName), priority))
        manifests = sorted(manifests, key=lambda manifest: manifest[1], reverse=True)
        self._log.debug('Manifests found: {0}'.format(manifests))
        if not manifests:
            raise ToolsError('No manifest file found in "{0}" or subdirectories'.format(os.path.abspath(self.path)))

        manifest, priority = manifests[0]
        manifestPath = os.path.abspath(os.path.join(self.path, manifest))

        # Pack all
        repositoryPath = tempfile.mkdtemp()
        shutil.copytree(self.path, os.path.join(repositoryPath, 'repo'))
        packagePath = os.path.join(repositoryPath, 'package.tar.gz')
        with tarfile.open(packagePath, mode='w:gz') as tar:
            tar.add(repositoryPath, arcname='')

        # Upload
        yield AppUploadAction(self.storage, **{
            'name': self.name,
            'manifest': manifestPath,
            'package': packagePath
        }).execute()
        yield 'Application {0} has been successfully uploaded'.format(self.name)

