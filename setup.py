import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="chatapi",
    version="0.1.2",
    author="Arseniy Banayev",
    author_email="arseniy.banayev@gmail.com",
    description="Python Chat API for Python applications that need instant messaging",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="chat whatsapp messaging",
    url="https://github.com/arseniybanayev/chatapi",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Topic :: Communications :: Chat",
        "Typing :: Typed"
    ],
    python_requires=">=3.6",
    
    # Same as in requirements.txt
    install_requires=["grpclib", "protobuf"]
)