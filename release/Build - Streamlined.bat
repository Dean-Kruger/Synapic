echo off && cls
cd "C:\Users\deank\sourcecode\Synapic\release"
python -m nuitka --product-name=Synapic --output-filename=Synapic --file-version=1.0 --company-name="Dean Kruger" --standalone --enable-plugin=tk-inter --module-parameter=torch-disable-jit=no --windows-console-mode=disable --windows-icon-from-ico="C:/Users/deank/sourcecode/Synapic/release/Icon.ico" --nofollow-import-to=tensorflow --nofollow-import-to=jax --nofollow-import-to=flax --nofollow-import-to=keras --msvc=latest C:\Users\deank\sourcecode\Synapic\main.py
rmdir /s /q "C:\Users\deank\sourcecode\Synapic\release\main.build"
pause
del "C:\Users\deank\sourcecode\Synapic\release\Build.bat"