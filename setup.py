from setuptools import setup, find_packages

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
    scripts=["app.py"],
    packages=find_packages(),
    python_requires=">=3.5",
    install_requires=[
        'urwid>2',
        'pyperclip',
        'requests',
        'slackclient',
        'urwid_readline'
    ]
)
