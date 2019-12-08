from setuptools import find_packages, setup

with open('README.md', 'r') as readme:
    long_description = readme.read()

setup(
    name='sclack',
    version='2.0',
    license='GPL3',
    description='The best CLI client for Slack, because everything is terrible',
    long_description=long_description,
    author='Marcelo Camargo',
    author_email='marcelocamargo@linuxmail.org',
    url='https://github.com/haskellcamargo/sclack',
    entry_points={'console_scripts': ['sclack=sclack.app:run']},
    package_data={'sclack': ['resources/*.json', 'resources/*.png']},
    packages=find_packages(),
    install_requires=[
        'asyncio',
        'urwid>2',
        'pyperclip',
        'requests',
        'slackclient==1.2.1',
        'urwid_readline'
    ],
    zip_safe=False,
)
