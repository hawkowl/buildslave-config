import os
from cStringIO import StringIO

from fabric.api import run, put, settings, env
from fabric.contrib.files import upload_template

from braid import package, pip, users, info
from braid.twisted import service

from twisted.python.filepath import FilePath

from braid import config

__all__ = ['config']

env.python = 'system'


packageEquivs = {
        'fedora': {
            'python-gmpy': 'gmpy',
            'python-subvertpy': 'subvertpy',
            'python-gobject': 'pygobject2',
            'python-soappy': 'SOAPpy',
            'python-dev': 'python-devel',
        },
        'debian': {},
        }


class Buildslave(service.Service):

    logDir = '~/run'

    def task_install(self,
                slavename,
                hostInfo,
                buildmaster='buildbot.twistedmatrix.com',
                port=9987,
                adminInfo='Tom Prince <buildbot@twistedmatrix.com>'):
        """
        Install buildslave
        """
        # Twisted's dependencies
        # (ubuntu/debian version)
        package.install([
            packageEquivs[info.distroFamily()].get(pkg, pkg)
            for pkg in
            'python-pyasn1',
            'python-crypto',
            'python-gmpy',
            'python-gobject',
            'python-soappy',
            #'python-subunit',
            'python-dev',
            'bzr',
            'gcc',
            'subversion',
            'python-pip',
            ])

        # rpmbuild
        # pydoctor
        # latex
        # subunit

        # Create home directory in default dir to avoid selinux issues.
        users.createService(self.serviceUser, base=None, groups=[])
        users.uploadLaunchpadKeys(self.serviceUser, 'tom.prince')
        self.bootstrap(python='system')

        with settings(user='buildslave'):
            pip.install('bzr-svn', python='system')
            pip.install('buildbot-slave', python='system')
            pip.install('--upgrade --force-reinstall bzr+https://code.launchpad.net/~mwhudson/pydoctor/dev@600#egg=pydoctor', python='system')
            pip.install(" ".join([
                'pep8==1.3.3',
                'pylint==0.25.1',
                'logilab-astng==0.23.1',
                'logilab-common==0.59.0'
                ]), python='system')

            tacFile = FilePath(__file__).sibling('buildbot.tac')
            upload_template(tacFile.path, os.path.join(self.runDir, 'buildbot.tac'),
                    context={
                        'buildmaster': buildmaster,
                        'port': port,
                        'slavename': slavename,
                        })

            infoPath = os.path.join(self.runDir, 'info')
            run('mkdir -p {}'.format(infoPath))
            put(StringIO(adminInfo), os.path.join(infoPath, 'admin'))
            put(StringIO(hostInfo), os.path.join(infoPath, 'host'))

            startFile = FilePath(__file__).sibling('start')
            put(startFile.path, os.path.join(self.binDir, 'start'), mode=0755)

from braid.tasks import addTasks
addTasks(globals(), Buildslave('buildslave').getTasks())
