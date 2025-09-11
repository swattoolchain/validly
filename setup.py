from setuptools import setup, find_packages

setup(
    name='Validly',
    version='1.0.22',
    author='Dinesh RVL',
    author_email='swat.github@gmail.com',
    description='A powerful and extensible data validation and comparison tool for developers and testers.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/swattoolchain/validly',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing'
    ],
    python_requires='>=3.6',
    install_requires=['requests']
)
