import os
import customtkinter

ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('release', 'release'), (ctk_path, 'customtkinter')],
    hiddenimports=[
        # Transformers and related
        'transformers',
        'transformers.models',
        'transformers.models.auto',
        'transformers.models.auto.modeling_auto',
        'transformers.models.auto.tokenization_auto',
        'transformers.models.auto.processing_auto',
        'transformers.pipelines',
        'transformers.utils',
        'transformers.image_utils',
        'huggingface_hub',
        'huggingface_hub.file_download',
        'huggingface_hub.hf_api',
        # Tokenizers
        'tokenizers',
        'sentencepiece',
        # Image processing
        'PIL',
        'PIL.Image',
        'piexif',
        'iptcinfo3',
        # PyTorch core
        'torch',
        'torch.nn',
        'torch.nn.functional',
        'torchvision',
        'torchvision.transforms',
        # Timm for vision models
        'timm',
        'timm.models',
        # Accelerate
        'accelerate',
        # Qwen VL utils
        'qwen_vl_utils',
        # Encoding/serialization
        'packaging',
        'packaging.version',
        'filelock',
        'safetensors',
        'regex',
        'requests',
        'tqdm',
        # Standard library items that may be missed
        'json',
        'logging',
        'threading',
        'queue',
        'dataclasses',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'scipy',
        'pandas',
        'numpy.distutils',
        'setuptools',
        'pytest',
        'IPython',
        'jupyter',
        'notebook',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Synapic',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='release/Icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Synapic',
)
