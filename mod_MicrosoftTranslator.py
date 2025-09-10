# -*- coding: utf-8 -*-
"""
MICROSOFT TRANSLATOR - UNIFIED CHAT TRANSLATOR
Using Microsoft Translator API for better language detection
Open Source Version - Configure via environment variables
"""
import BigWorld
import urllib2  
import urllib
import json
import threading
import time
import os
import re
from threading import RLock
from datetime import datetime

# Configuration from environment variables or defaults
API_KEY = os.environ.get('MICROSOFT_TRANSLATOR_KEY', 'YOUR_API_KEY_HERE')
API_REGION = os.environ.get('MICROSOFT_TRANSLATOR_REGION', 'YOUR_REGION_HERE')
API_URL = 'https://api.cognitive.microsofttranslator.com/translate'
API_VERSION = '3.0'
TARGET_LANG = 'en'  # Microsoft uses 'en' not 'EN'
QUICK_TIMEOUT = 1.5

# Check if API key is configured
if API_KEY == 'YOUR_API_KEY_HERE':
    print('[MSTranslator] WARNING: API key not configured!')
    print('[MSTranslator] Please set MICROSOFT_TRANSLATOR_KEY environment variable')
    print('[MSTranslator] Or edit this file and replace YOUR_API_KEY_HERE')

# Cache and state management
translation_cache = {}
cache_lock = RLock()
pending_messages = {}
message_counter = 0
log_file = None
initialized = False

# Common English words for detection
COMMON_ENGLISH_WORDS = set([
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
    'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their',
    'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go',
    'me', 'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know',
    'take', 'people', 'into', 'year', 'your', 'good', 'some', 'could', 'them',
    'see', 'other', 'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over',
    'think', 'also', 'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first',
    'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day',
    'most', 'us', 'is', 'was', 'are', 'been', 'has', 'had', 'were', 'said', 'did',
    'here', 'there', 'where', 'why', 'how', 'what', 'when', 'who', 'which'
])

def logDebug(message):
    """Write to log file for debugging"""
    global log_file
    try:
        if log_file is None:
            log_path = os.path.join(os.getcwd(), 'microsoft_translator.log')
            log_file = open(log_path, 'a')
            log_file.write('\n' + '='*60 + '\n')
            log_file.write('Microsoft Translator Started: %s\n' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            log_file.write('='*60 + '\n')
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_file.write('[%s] %s\n' % (timestamp, message))
        log_file.flush()
    except:
        pass

def init():
    """Initialize the mod"""
    global initialized
    
    if initialized:
        print('[MSTranslator] Already initialized, skipping...')
        return
    
    initialized = True
    logDebug('Starting Microsoft Chat Translator...')
    print('[MSTranslator] Starting Microsoft Chat Translator...')
    BigWorld.callback(1.0, hookChat)
    BigWorld.callback(2.0, showNotification)

def showNotification():
    """Show notification"""
    try:
        from gui.SystemMessages import pushMessage, SM_TYPE
        pushMessage('Microsoft Chat Translator Active', type=SM_TYPE.Information)
        print('[MSTranslator] Notification shown')
    except Exception as e:
        print('[MSTranslator] Could not show notification: %s' % str(e))

def isLikelyEnglish(text):
    """Check if text is likely already in English"""
    # Remove special characters and convert to lowercase
    clean_text = re.sub(r'[^\w\s]', '', text.lower())
    words = clean_text.split()
    
    if not words:
        return False
    
    # Count how many words are common English words
    english_word_count = sum(1 for word in words if word in COMMON_ENGLISH_WORDS)
    
    # If more than 50% of words are common English words, it's likely English
    english_ratio = float(english_word_count) / len(words)
    
    logDebug('English detection for "%s": %d/%d words = %.2f ratio' % 
             (text[:30], english_word_count, len(words), english_ratio))
    
    # Also check for common English phrases
    if english_ratio >= 0.5:
        return True
    
    # Check for common English gaming phrases
    english_phrases = [
        'gg', 'gl hf', 'good game', 'nice shot', 'well played',
        'thank you', 'thanks', 'sorry', 'my bad', 'no problem',
        'let\'s go', 'follow me', 'help', 'attack', 'defend',
        'fall back', 'push', 'rush', 'camp', 'spot'
    ]
    
    lower_text = text.lower()
    for phrase in english_phrases:
        if phrase in lower_text:
            logDebug('Found English phrase: %s' % phrase)
            return True
    
    return False

def hookChat():
    """Hook all chat systems"""
    print('[MSTranslator] Installing hooks...')
    logDebug('Installing hooks...')
    
    # Hook standard controllers with async
    hookStandardControllers()
    
    # Hook platoon system with sync (proven to work)
    hookPlatoonSystemSync()
    
    print('[MSTranslator] Ready! All chats will be translated.')

def hookStandardControllers():
    """Hook standard chat controllers with async translation"""
    try:
        from messenger.gui.Scaleform.channels.bw_chat2 import lobby_controllers, battle_controllers
        
        def create_hook(orig, controller_name):
            """Create async delayed translation hook"""
            def hooked_method(self, message, *args, **kwargs):
                if hasattr(message, 'text') and message.text:
                    original_text = message.text
                    
                    # Skip if already translated
                    if '→en]' in original_text.lower():
                        return orig(self, message, *args, **kwargs)
                    
                    # Check if text is likely English
                    if isLikelyEnglish(original_text):
                        logDebug('%s: Text is English, skipping: %s' % (controller_name, original_text[:50]))
                        return orig(self, message, *args, **kwargs)
                    
                    # Check cache first
                    with cache_lock:
                        if original_text in translation_cache:
                            cached = translation_cache[original_text]
                            if cached:
                                message.text = cached
                                print('[MSTranslator] Cache hit: %s' % cached[:50])
                                return orig(self, message, *args, **kwargs)
                            else:
                                return orig(self, message, *args, **kwargs)
                    
                    # Start async translation
                    message_id = getMessageId()
                    pending_messages[message_id] = {
                        'message': message,
                        'original_text': original_text,
                        'controller': self,
                        'args': args,
                        'kwargs': kwargs,
                        'orig_method': orig
                    }
                    
                    thread = threading.Thread(target=translateAsyncDelayed, args=(original_text, message_id))
                    thread.daemon = True
                    thread.start()
                    
                    BigWorld.callback(8.0, lambda: fallbackDisplay(message_id, original_text))
                    
                    # Don't display yet
                    return
                
                return orig(self, message, *args, **kwargs)
            return hooked_method
        
        # Training room chat
        if hasattr(lobby_controllers, 'TrainingChannelController'):
            original_training = lobby_controllers.TrainingChannelController.addMessage
            lobby_controllers.TrainingChannelController.addMessage = create_hook(original_training, 'Training')
            print('[MSTranslator] Hooked Training')
            logDebug('Hooked TrainingChannelController')
        
        # Battle team chat
        if hasattr(battle_controllers, 'TeamChannelController'):
            original_battle = battle_controllers.TeamChannelController.addMessage
            battle_controllers.TeamChannelController.addMessage = create_hook(original_battle, 'BattleTeam')
            print('[MSTranslator] Hooked Battle Team')
            logDebug('Hooked TeamChannelController')
        
        # Battle all chat
        if hasattr(battle_controllers, 'CommonChannelController'):
            original_common = battle_controllers.CommonChannelController.addMessage
            battle_controllers.CommonChannelController.addMessage = create_hook(original_common, 'BattleAll')
            print('[MSTranslator] Hooked Battle All')
            logDebug('Hooked CommonChannelController')
        
    except Exception as e:
        print('[MSTranslator] Standard hook error: %s' % str(e))
        logDebug('Standard hook error: %s' % str(e))

def hookPlatoonSystemSync():
    """Hook platoon chat with SYNC translation (proven to work)"""
    try:
        from messenger.proto.bw_chat2.entities import BWUnitChannelEntity
        
        # Hook BWUnitChannelEntity.addMessage
        if hasattr(BWUnitChannelEntity, 'addMessage'):
            original_add = BWUnitChannelEntity.addMessage
            
            def hooked_add(self, message):
                if hasattr(message, 'text') and message.text:
                    original_text = message.text
                    logDebug('BWUnitChannelEntity.addMessage: %s' % original_text)
                    
                    # Skip if already translated
                    if '→en]' in original_text.lower():
                        return original_add(self, message)
                    
                    # Check if text is likely English
                    if isLikelyEnglish(original_text):
                        logDebug('Platoon: Text is English, skipping: %s' % original_text[:50])
                        return original_add(self, message)
                    
                    # Check cache
                    with cache_lock:
                        if original_text in translation_cache:
                            cached = translation_cache[original_text]
                            if cached:
                                message.text = cached
                                logDebug('Platoon cache hit: %s' % cached[:50])
                            return original_add(self, message)
                    
                    # Translate synchronously for platoon (simpler, works)
                    translated = translateQuickMicrosoft(original_text)
                    if translated:
                        message.text = translated
                        logDebug('Translated platoon: %s' % translated[:50])
                
                return original_add(self, message)
            
            BWUnitChannelEntity.addMessage = hooked_add
            print('[MSTranslator] Hooked BWUnitChannelEntity (Platoon) - SYNC mode')
            logDebug('Hooked BWUnitChannelEntity.addMessage - SYNC mode')
        
        # Also hook UnitChannelController as backup
        from messenger.gui.Scaleform.channels.bw_chat2.lobby_controllers import UnitChannelController
        if hasattr(UnitChannelController, 'addMessage'):
            original_unit = UnitChannelController.addMessage
            
            def hooked_unit(self, message, *args, **kwargs):
                if hasattr(message, 'text') and message.text:
                    if '→en]' not in message.text.lower() and not isLikelyEnglish(message.text):
                        # Use quick translation as backup
                        translated = translateQuickMicrosoft(message.text)
                        if translated:
                            message.text = translated
                
                return original_unit(self, message, *args, **kwargs)
            
            UnitChannelController.addMessage = hooked_unit
            print('[MSTranslator] Hooked UnitChannelController (backup)')
            logDebug('Hooked UnitChannelController')
            
    except Exception as e:
        print('[MSTranslator] Platoon hook error: %s' % str(e))
        logDebug('Platoon hook error: %s' % str(e))

def getMessageId():
    """Generate unique message ID"""
    global message_counter
    message_counter += 1
    return message_counter

def translateQuickMicrosoft(text):
    """Quick sync translation using Microsoft API"""
    try:
        # Check cache
        with cache_lock:
            if text in translation_cache:
                return translation_cache[text]
        
        logDebug('Quick translating: %s' % text)
        
        # Prepare Microsoft API request
        url = '%s?api-version=%s&to=%s' % (API_URL, API_VERSION, TARGET_LANG)
        
        # Request body is an array of text objects
        body = json.dumps([{'Text': text}])
        
        logDebug('Microsoft API request: %s' % body)
        
        request = urllib2.Request(url, body)
        request.add_header('Ocp-Apim-Subscription-Key', API_KEY)
        request.add_header('Ocp-Apim-Subscription-Region', API_REGION)
        request.add_header('Content-Type', 'application/json; charset=UTF-8')
        
        response = urllib2.urlopen(request, timeout=QUICK_TIMEOUT)
        response_text = response.read()
        logDebug('Microsoft API response: %s' % response_text[:200])
        
        result = json.loads(response_text)
        
        if result and len(result) > 0:
            item = result[0]
            
            # Get detected language
            detected_lang = '??'
            confidence = 0.0
            if 'detectedLanguage' in item:
                detected_lang = item['detectedLanguage'].get('language', '??').upper()
                confidence = item['detectedLanguage'].get('score', 0.0)
                logDebug('Detected language: %s (confidence: %.2f)' % (detected_lang, confidence))
            
            # Get translation
            if 'translations' in item and len(item['translations']) > 0:
                translated_text = item['translations'][0]['text']
                
                # Check if translation is identical (untranslatable)
                if translated_text.lower() == text.lower():
                    logDebug('Translation identical to original, skipping')
                    with cache_lock:
                        translation_cache[text] = None
                    return None
                
                # Don't translate if detected as English with high confidence
                if detected_lang == 'EN' and confidence > 0.85:
                    logDebug('Detected as English with high confidence, skipping')
                    with cache_lock:
                        translation_cache[text] = None
                    return None
                
                # Format and cache
                formatted = '[%s→en] %s | %s' % (detected_lang, translated_text, text)
                
                with cache_lock:
                    translation_cache[text] = formatted
                    if len(translation_cache) > 100:
                        for key in translation_cache.keys()[:20]:
                            del translation_cache[key]
                
                return formatted
            
    except urllib2.HTTPError as e:
        error_body = e.read() if hasattr(e, 'read') else ''
        logDebug('Microsoft HTTP error %s: %s. Body: %s' % (e.code, str(e), error_body))
    except Exception as e:
        logDebug('Microsoft translation error: %s' % str(e))
    
    return None

def translateAsyncDelayed(text, message_id):
    """Async translation for standard chat using Microsoft API"""
    try:
        print('[MSTranslator] Async translating: %s' % text[:30])
        
        # Prepare Microsoft API request
        url = '%s?api-version=%s&to=%s' % (API_URL, API_VERSION, TARGET_LANG)
        
        # Request body is an array of text objects
        body = json.dumps([{'Text': text}])
        
        logDebug('Async Microsoft API request: %s' % body)
        
        request = urllib2.Request(url, body)
        request.add_header('Ocp-Apim-Subscription-Key', API_KEY)
        request.add_header('Ocp-Apim-Subscription-Region', API_REGION)
        request.add_header('Content-Type', 'application/json; charset=UTF-8')
        
        response = urllib2.urlopen(request, timeout=5.0)
        response_text = response.read()
        logDebug('Async Microsoft API response: %s' % response_text[:300])
        
        result = json.loads(response_text)
        
        if result and len(result) > 0:
            item = result[0]
            
            # Get detected language
            detected_lang = '??'
            confidence = 0.0
            if 'detectedLanguage' in item:
                detected_lang = item['detectedLanguage'].get('language', '??').upper()
                confidence = item['detectedLanguage'].get('score', 0.0)
            
            # Get translation
            if 'translations' in item and len(item['translations']) > 0:
                translated_text = item['translations'][0]['text']
                
                print('[MSTranslator] Lang: %s (%.2f), Original: %s, Translated: %s' % 
                      (detected_lang, confidence, text, translated_text))
                
                # Check if translation is identical (untranslatable)
                if translated_text.lower() == text.lower():
                    logDebug('Translation identical to original, displaying as-is')
                    with cache_lock:
                        translation_cache[text] = None
                    BigWorld.callback(0.1, lambda: displayMessage(message_id, text))
                    return
                
                # Don't translate if English with high confidence
                if detected_lang == 'EN' and confidence > 0.85:
                    logDebug('Detected as English by API, displaying original')
                    with cache_lock:
                        translation_cache[text] = None
                    BigWorld.callback(0.1, lambda: displayMessage(message_id, text))
                    return
                
                # Format and cache
                formatted = '[%s→en] %s | %s' % (detected_lang, translated_text, text)
                
                with cache_lock:
                    translation_cache[text] = formatted
                    if len(translation_cache) > 100:
                        for key in translation_cache.keys()[:20]:
                            del translation_cache[key]
                
                BigWorld.callback(0.1, lambda: displayMessage(message_id, formatted))
        
    except urllib2.HTTPError as e:
        error_body = e.read() if hasattr(e, 'read') else ''
        print('[MSTranslator] Async HTTP error %s: %s. Body: %s' % (e.code, str(e), error_body[:200]))
        logDebug('Async HTTP error: %s' % error_body)
        with cache_lock:
            translation_cache[text] = None
        BigWorld.callback(0.1, lambda: displayMessage(message_id, text))
        
    except Exception as e:
        print('[MSTranslator] Async translation error: %s' % str(e))
        with cache_lock:
            translation_cache[text] = None
        BigWorld.callback(0.1, lambda: displayMessage(message_id, text))

def fallbackDisplay(message_id, original_text):
    """Fallback display for timeout"""
    if message_id in pending_messages:
        print('[MSTranslator] Fallback display for message %s: %s' % (message_id, original_text))
        displayMessage(message_id, original_text)

def displayMessage(message_id, text):
    """Display the message"""
    try:
        if message_id not in pending_messages:
            print('[MSTranslator] Warning: Message %s not found in pending' % message_id)
            return
            
        msg_data = pending_messages[message_id]
        
        message = msg_data['message']
        controller = msg_data['controller']
        args = msg_data.get('args', ())
        kwargs = msg_data.get('kwargs', {})
        orig_method = msg_data['orig_method']
        
        message.text = text
        print('[MSTranslator] Displaying: %s' % text[:50])
        
        try:
            orig_method(controller, message, *args, **kwargs)
        except Exception as e:
            print('[MSTranslator] Error calling original method: %s' % str(e))
            try:
                controller.addMessage(message, *args, **kwargs)
            except:
                print('[MSTranslator] Fallback display also failed')
        
        del pending_messages[message_id]
        
    except Exception as e:
        print('[MSTranslator] Display message error: %s' % str(e))

# Initialize
init()
print('[MSTranslator] Microsoft translator loaded!')