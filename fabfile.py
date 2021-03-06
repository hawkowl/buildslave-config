"""
"""
from os import path
import imp
from cStringIO import StringIO

from fabric.api import run, put, settings, env
from braid.api import sudo
from fabric.contrib.files import upload_template

from braid import package, pip, users, info
from braid.twisted import service

from twisted.python.filepath import FilePath

from braid import config

__all__ = ['config']


def loadPrivateData(base=__file__):
    privateDir = FilePath(base).sibling('private')
    privateFile = privateDir.child('private.py')
    if privateFile.exists():
         return imp.load_source('private',
                                privateFile.path,
                                privateFile.open())
    else:
        return None


def passwordFromPrivateData(slaveName):
    private = loadPrivateData()
    if private:
        return private.bot_info[slaveName][0]
    else:
        return None

env.python = 'system'

packageEquivs = {
        'fedora': {
            'python-gmpy': 'gmpy',
            'python-gobject': 'pygobject2',
            'python-soappy': 'SOAPpy',
            'python-dev': 'python-devel',
            'g++': 'gcc-c++',
            'python-openssl': 'pyOpenSSL',
        },
        'debian': {
            'texlive': 'texlive-latex-base',
            'gmp-devel': 'libgmp3-dev',
            'cppunit-devel': 'libcppunit-dev',
            'perl-devel': 'libperl-dev',
            'netpbm-progs': 'netpbm',
            'hg': 'mercurial',
            'libffi-devel': 'libffi-dev',
            'openssl-devel': 'libssl-dev',
            'ncurses-devel': 'libncurses5-dev',
            'expat-devel': 'libexpat1-dev',
            'sqlite-devel': 'libsqlite3-dev',
            'zlib-devel': 'zlib1g-dev',
            'bzip2-devel': 'libbz2-dev',
            'check-devel': 'check',
        },
}


class Buildslave(service.Service):
    """
    """

    logDir = '~/run'

    def setUser(self, slavename=None):
        env.user = env.slaves[env.host][2]


    def task_install(self,
                slavename=None,
                hostInfo=None,
                buildmaster='buildbot.twistedmatrix.com',
                port=9987,
                adminInfo='Tom Prince <buildbot@twistedmatrix.com>',
                password=None):
        """
        Install buildslave
        """

        self.setUser(slavename)
        if slavename is None:
            slavename = env.slaves[env.host][0]

        if password is None:
            password = passwordFromPrivateData(slavename)

        # Twisted's dependencies
        # (ubuntu/debian version)
        package.update()
        package.install([
            packageEquivs[info.distroFamily()].get(pkg, pkg)
            for pkg in
            'python-pyasn1',
            'python-crypto',
            'python-gmpy',
            'python-gobject',
            'python-soappy',
            'python-subunit',
            'python-openssl',
            'python-dev',
            'bzr',
            'git',
            'gcc',
            'subversion',
            'python-subvertpy',
            'python-pip',
            # cpython translator
            'make',
            'gmp-devel',
            # subunit
            'cppunit-devel',
            'check-devel',
            'g++',
            'perl-devel',
            # Docs
            'texlive',
            'netpbm-progs',
            'bzip2',
            'python-sphinx',
            # For pypy translator
            'hg',
            'libffi-devel',
            'openssl-devel',
            'ncurses-devel',
            'expat-devel',
            'sqlite-devel',
            'zlib-devel',
            'bzip2-devel',
            ])

        # rpmbuild
        # subunit

        # Create home directory in default dir to avoid selinux issues.
        users.createService(self.serviceUser, base=None, groups=[])
        users.uploadLaunchpadKeys(self.serviceUser, 'tom.prince')

        pipPath = '~/.local/bin/pip'
        with settings(user='buildslave'):
            pip.bootstrap(pipPath)

        self.bootstrap(python='system')

        with settings(user='buildslave'):
            pip.install('bzr-svn', pip=pipPath)
            pip.install('buildbot-slave', pip=pipPath)
            pip.install(" ".join([
                'pydoctor==0.5b2',
                'pep8==1.3.3',
                'pylint==0.25.1',
                'logilab-astng==0.23.1',
                'logilab-common==0.59.0',
                #'https://launchpad.net/pyflakes/main/0.5.0/+download/pyflakes-0.5.0.tar.gz',
                'pyflakes==0.7.3',
                'cffi',
                ]), pip=pipPath)

            tacFile = FilePath(__file__).sibling('buildbot.tac')
            upload_template(tacFile.path, path.join(self.runDir, 'buildbot.tac'),
                    context={
                        'buildmaster': buildmaster,
                        'port': port,
                        'slavename': slavename,
                        })

            infoPath = path.join(self.runDir, 'info')
            run('mkdir -p {}'.format(infoPath))
            put(StringIO(adminInfo), path.join(infoPath, 'admin'))
            if hostInfo is None:
                hostInfo = run('uname -a', combine_stderr=False)
            put(StringIO(hostInfo), path.join(infoPath, 'host'))

            startFile = FilePath(__file__).sibling('start')
            put(startFile.path, path.join(self.binDir, 'start'), mode=0755)

            if password is not None:
                put(StringIO(password), path.join(self.runDir, 'slave.passwd'), mode=0700)


    def task_iptables(self):
        """
        Run iptables.
        """
        self.setUser()
        sudo('iptables -I INPUT --dest 224.0.0.0/4 -j ACCEPT')


    def task_tapdevice(self):
        """
        Create tap devices for tests.
        """
        self.setUser()

        name = "twtest"

        # A tap device without protocol information
        sudo('ip tuntap add dev tap-{} mode tap user buildslave'.format(name))
        sudo('ip link set up dev tap-{}'.format(name))
        sudo('ip addr add 172.16.0.1/24 dev tap-{}'.format(name))
        sudo('ip neigh add 172.16.0.2 lladdr de:ad:be:ef:ca:fe dev tap-{}'.format(name))
        sudo('iptables -I INPUT --dest 172.16.0.1 -j ACCEPT')

        # A tap device with protocol information
        sudo('ip tuntap add dev tap-{}-pi mode tap user buildslave'.format(name))
        sudo('ip link set up dev tap-{}-pi'.format(name))
        sudo('ip addr add 172.16.1.1/24 dev tap-{}-pi'.format(name))
        sudo('ip neigh add 172.16.1.2 lladdr de:ad:ca:fe:be:ef dev tap-{}-pi'.format(name))
        sudo('iptables -I INPUT --dest 172.16.1.1 -j ACCEPT')

        # A tun device without protocol information
        sudo('ip tuntap add dev tun-{} mode tun user buildslave'.format(name))
        sudo('ip link set up dev tun-{}'.format(name))

        # A tun device with protocol information
        sudo('ip tuntap add dev tun-{}-pi mode tun user buildslave'.format(name))
        sudo('ip link set up dev tun-{}-pi'.format(name))


from braid.tasks import addTasks
addTasks(globals(), Buildslave('buildslave').getTasks())
