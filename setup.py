from setuptools import setup

with open('README.md', 'r') as readme:
    long_description = readme.read()

setup(
    name='sclack',
    version='1.0',
    license='GPL3',
    description='The best CLI client for Slack, because everything is terrible',
    long_description=long_description,
    author='Marcelo Camargo',
    author_email='marcelocamargo@linuxmail.org',
    url='https://github.com/haskellcamargo/sclack',
    packages=['sclack'],
    entry_points={
        'console_scripts': ['sclack=sclack.__main__:main'],
    },
    install_requires=[
        'asyncio',
        'urwid>2',
        'pyperclip',
        'requests',
        'slackclient'
    ]
)
