#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Build script for WoT Chat Translator"""
import zipfile
import os
import py_compile
import sys

def build_translator():
    """Build the Chat Translator .wotmod package"""
    
    # Check for environment variables
    api_key = os.environ.get('MICROSOFT_TRANSLATOR_KEY', 'YOUR_API_KEY_HERE')
    api_region = os.environ.get('MICROSOFT_TRANSLATOR_REGION', 'YOUR_REGION_HERE')
    
    if api_key == 'YOUR_API_KEY_HERE':
        print('=' * 60)
        print('WARNING: API key not configured!')
        print('Please set environment variables:')
        print('  MICROSOFT_TRANSLATOR_KEY=<your_key>')
        print('  MICROSOFT_TRANSLATOR_REGION=<your_region>')
        print('')
        print('Or edit mod_MicrosoftTranslator.py directly')
        print('=' * 60)
        print('')
    
    # Ensure build directory exists
    if not os.path.exists('build'):
        os.makedirs('build')
    
    wotmod_name = 'ChatTranslator.wotmod'
    wotmod_path = os.path.join('build', wotmod_name)
    
    print('Building WoT Chat Translator...')
    print('=' * 60)
    
    # Compile the mod
    mod_py = 'mod_MicrosoftTranslator.py'
    mod_pyc = 'mod_MicrosoftTranslator.pyc'
    
    if os.path.exists(mod_py):
        print('Compiling %s...' % mod_py)
        try:
            py_compile.compile(mod_py, mod_pyc, doraise=True)
            print('  Compilation successful')
        except py_compile.PyCompileError as e:
            print('  ERROR: Compilation failed!')
            print('  %s' % str(e))
            return None
    else:
        print('ERROR: %s not found!' % mod_py)
        return None
    
    # Create the wotmod package
    with zipfile.ZipFile(wotmod_path, 'w', zipfile.ZIP_STORED) as zf:
        
        # Add compiled mod
        if os.path.exists(mod_pyc):
            zf.write(mod_pyc, 'res/scripts/client/gui/mods/mod_MicrosoftTranslator.pyc')
            print('  Added: res/scripts/client/gui/mods/mod_MicrosoftTranslator.pyc')
        else:
            # Fallback to source if compilation failed
            zf.write(mod_py, 'res/scripts/client/gui/mods/mod_MicrosoftTranslator.py')
            print('  Added: res/scripts/client/gui/mods/mod_MicrosoftTranslator.py (source)')
        
        # Create meta.xml
        meta_xml = '''<root>
	<id>wot.chatTranslator</id>
	<version>2.0.0</version>
	<name>Chat Translator</name>
	<description>Translates chat messages using Microsoft Translator API</description>
</root>'''
        zf.writestr('meta.xml', meta_xml)
        print('  Added: meta.xml')
    
    # Clean up compiled file
    if os.path.exists(mod_pyc):
        os.remove(mod_pyc)
        print('  Cleaned up temporary .pyc file')
    
    size_kb = os.path.getsize(wotmod_path) / 1024.0
    
    print('\n' + '=' * 60)
    print('SUCCESS! Created %s (%.1f KB)' % (wotmod_name, size_kb))
    print('=' * 60)
    print('\nFeatures:')
    print('  ✓ Microsoft Translator API')
    print('  ✓ Automatic language detection')
    print('  ✓ Async for battle/training chat (no lag)')
    print('  ✓ Sync for platoon chat')
    print('  ✓ Smart English detection')
    print('  ✓ Translation caching (4 hour expiry)')
    print('  ✓ Rate limiting (200 translations/hour per player)')
    print('\nInstall to: World_of_Tanks/mods/<game_version>/')
    print('Example: World_of_Tanks/mods/2.0.0.0/')
    
    return wotmod_path

if __name__ == '__main__':
    build_translator()