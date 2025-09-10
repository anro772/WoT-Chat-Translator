# -*- coding: utf-8 -*-
"""
MICROSOFT TRANSLATOR - UNIFIED CHAT TRANSLATOR WITH RATE LIMITING
Using Microsoft Translator API with comprehensive rate limiting
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
from collections import deque, defaultdict

# Configuration - Replace these with your actual Microsoft Translator API credentials
API_KEY = 'YOUR_API_KEY_HERE'  # Replace with your API key from Azure Portal
API_REGION = 'YOUR_REGION_HERE'  # Replace with your region (e.g., 'eastus', 'switzerlandnorth')
API_URL = 'https://api.cognitive.microsofttranslator.com/translate'
API_VERSION = '3.0'
TARGET_LANG = 'en'  # Microsoft uses 'en' not 'EN'
QUICK_TIMEOUT = 1.5

# RATE LIMITING CONFIGURATION
RATE_LIMITS = {
    'PER_PLAYER_HOURLY': 200,      # Per player per hour (generous for legit use)
    'CACHE_EXPIRE_HOURS': 4,       # How long to cache translations
    'BLACKLIST_THRESHOLD': 400,    # Hourly attempts before blacklisting
    'WARNING_THRESHOLD': 0.8       # Warn at 80% of limit
}

# Check if API key is configured
if API_KEY == 'YOUR_API_KEY_HERE':
    print('[MSTranslator] WARNING: API key not configured!')
    print('[MSTranslator] Please set MICROSOFT_TRANSLATOR_KEY environment variable')
    print('[MSTranslator] Or edit this file and replace YOUR_API_KEY_HERE')

# Cache and state management
translation_cache = {}
cache_timestamps = {}
cache_lock = RLock()
pending_messages = {}
message_counter = 0
log_file = None
initialized = False

# Rate limiting state
rate_limit_lock = RLock()
player_hourly_count = defaultdict(lambda: deque())  # Per-player hourly windows
blacklisted_players = set()
rate_limit_warnings = defaultdict(int)  # Track warnings shown

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
            log_file.write('Rate Limiting ENABLED - v2.0\n')
            log_file.write('='*60 + '\n')
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_file.write('[%s] %s\n' % (timestamp, message))
        log_file.flush()
    except:
        pass

def cleanupRateLimitWindows():
    """Clean up old entries from rate limit windows"""
    with rate_limit_lock:
        current_time = time.time()
        hour_ago = current_time - 3600
        
        # Clean per-player windows
        for player_name in list(player_hourly_count.keys()):
            # Clean hourly
            while player_hourly_count[player_name] and player_hourly_count[player_name][0] < hour_ago:
                player_hourly_count[player_name].popleft()
            
            # Remove empty deques
            if not player_hourly_count[player_name]:
                del player_hourly_count[player_name]

def checkRateLimit(player_name=None):
    """Check if translation is allowed under rate limits"""
    with rate_limit_lock:
        current_time = time.time()
        cleanupRateLimitWindows()
        
        # Check if player is blacklisted
        if player_name and player_name in blacklisted_players:
            logDebug('Player %s is blacklisted' % player_name)
            return False, "Player temporarily blocked due to excessive requests"
        
        # Check per-player limits if player_name provided
        if player_name:
            # Check per-player hourly limit
            player_hour_count = len(player_hourly_count[player_name])
            if player_hour_count >= RATE_LIMITS['PER_PLAYER_HOURLY']:
                logDebug('Player %s hourly limit reached: %d/%d' % (player_name, player_hour_count, RATE_LIMITS['PER_PLAYER_HOURLY']))
                
                # Check for blacklisting
                if player_hour_count >= RATE_LIMITS['BLACKLIST_THRESHOLD']:
                    blacklisted_players.add(player_name)
                    logDebug('Player %s added to blacklist' % player_name)
                
                return False, "Your hourly limit reached (200 translations). Get your own free API key!"
            
            # Check if approaching limits and show warning
            usage_ratio = float(player_hour_count) / RATE_LIMITS['PER_PLAYER_HOURLY']
            if usage_ratio >= RATE_LIMITS['WARNING_THRESHOLD']:
                if rate_limit_warnings[player_name] < 3:  # Max 3 warnings per player
                    rate_limit_warnings[player_name] += 1
                    showWarning("Translation limit approaching! Consider getting your own free API key.")
        
        return True, None

def recordTranslation(player_name=None):
    """Record a successful translation for rate limiting"""
    with rate_limit_lock:
        current_time = time.time()
        
        # Record in per-player windows if player_name provided
        if player_name:
            player_hourly_count[player_name].append(current_time)
            
            # Log current usage
            logDebug('Player %s - Hourly: %d/%d' % 
                     (player_name, len(player_hourly_count[player_name]), 
                      RATE_LIMITS['PER_PLAYER_HOURLY']))

def cleanExpiredCache():
    """Remove expired cache entries"""
    with cache_lock:
        current_time = time.time()
        expire_time = RATE_LIMITS['CACHE_EXPIRE_HOURS'] * 3600
        
        expired_keys = []
        for key, timestamp in cache_timestamps.items():
            if current_time - timestamp > expire_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del translation_cache[key]
            del cache_timestamps[key]
        
        if expired_keys:
            logDebug('Cleaned %d expired cache entries' % len(expired_keys))

def extractPlayerName(message):
    """Extract player name from message object"""
    try:
        if hasattr(message, 'playerName'):
            return message.playerName
        elif hasattr(message, 'fromName'):
            return message.fromName
        elif hasattr(message, 'accountName'):
            return message.accountName
        elif hasattr(message, 'userName'):
            return message.userName
        elif hasattr(message, 'data') and message.data:
            if 'playerName' in message.data:
                return message.data['playerName']
            elif 'fromName' in message.data:
                return message.data['fromName']
    except:
        pass
    return None

def showWarning(text):
    """Show warning message to player"""
    try:
        from gui.SystemMessages import pushMessage, SM_TYPE
        pushMessage(text, type=SM_TYPE.Warning)
    except:
        print('[MSTranslator] Warning: %s' % text)

def init():
    """Initialize the mod"""
    global initialized
    
    if initialized:
        print('[MSTranslator] Already initialized, skipping...')
        return
    
    initialized = True
    logDebug('Starting Microsoft Chat Translator with Rate Limiting...')
    print('[MSTranslator] Starting Microsoft Chat Translator with Rate Limiting...')
    BigWorld.callback(1.0, hookChat)
    BigWorld.callback(2.0, showNotification)
    
    # Start cache cleanup timer
    BigWorld.callback(600.0, periodicCleanup)  # Every 10 minutes

def periodicCleanup():
    """Periodic cleanup of caches and rate limit windows"""
    cleanExpiredCache()
    cleanupRateLimitWindows()
    
    # Log current status
    with rate_limit_lock:
        active_players = len(player_hourly_count)
        total_translations = sum(len(counts) for counts in player_hourly_count.values())
        logDebug('Status - Cache: %d entries, Active players: %d, Total translations: %d, Blacklisted: %d' % 
                 (len(translation_cache), active_players, total_translations, len(blacklisted_players)))
    
    # Schedule next cleanup
    BigWorld.callback(600.0, periodicCleanup)

def showNotification():
    """Show notification"""
    try:
        from gui.SystemMessages import pushMessage, SM_TYPE
        pushMessage('Microsoft Chat Translator Active (Rate Limited)', type=SM_TYPE.Information)
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
    
    print('[MSTranslator] Ready! All chats will be translated with rate limiting.')

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
                    
                    # Extract player name for rate limiting
                    player_name = extractPlayerName(message)
                    
                    # Check rate limit
                    allowed, error_msg = checkRateLimit(player_name)
                    if not allowed:
                        if error_msg:
                            message.text = '[LIMIT] %s' % error_msg
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
                        'orig_method': orig,
                        'player_name': player_name
                    }
                    
                    thread = threading.Thread(target=translateAsyncDelayed, args=(original_text, message_id, player_name))
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
                    
                    # Extract player name
                    player_name = extractPlayerName(message)
                    
                    # Check rate limit
                    allowed, error_msg = checkRateLimit(player_name)
                    if not allowed:
                        if error_msg:
                            message.text = '[LIMIT] %s' % error_msg
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
                    translated = translateQuickMicrosoft(original_text, player_name)
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
                        player_name = extractPlayerName(message)
                        
                        # Check rate limit
                        allowed, error_msg = checkRateLimit(player_name)
                        if allowed:
                            # Use quick translation as backup
                            translated = translateQuickMicrosoft(message.text, player_name)
                            if translated:
                                message.text = translated
                        elif error_msg:
                            message.text = '[LIMIT] %s' % error_msg
                
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

def translateQuickMicrosoft(text, player_name=None):
    """Quick sync translation using Microsoft API"""
    try:
        # Check cache
        with cache_lock:
            if text in translation_cache:
                return translation_cache[text]
        
        # Check rate limit before API call
        allowed, error_msg = checkRateLimit(player_name)
        if not allowed:
            logDebug('Rate limit hit for quick translation')
            return None
        
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
                        cache_timestamps[text] = time.time()
                    return None
                
                # Don't translate if detected as English with high confidence
                if detected_lang == 'EN' and confidence > 0.85:
                    logDebug('Detected as English with high confidence, skipping')
                    with cache_lock:
                        translation_cache[text] = None
                        cache_timestamps[text] = time.time()
                    return None
                
                # Format and cache
                formatted = '[%s→en] %s | %s' % (detected_lang, translated_text, text)
                
                with cache_lock:
                    translation_cache[text] = formatted
                    cache_timestamps[text] = time.time()
                    
                    # Clean old cache entries if too many
                    if len(translation_cache) > 200:
                        cleanExpiredCache()
                
                # Record successful translation
                recordTranslation(player_name)
                
                return formatted
            
    except urllib2.HTTPError as e:
        error_body = e.read() if hasattr(e, 'read') else ''
        logDebug('Microsoft HTTP error %s: %s. Body: %s' % (e.code, str(e), error_body))
    except Exception as e:
        logDebug('Microsoft translation error: %s' % str(e))
    
    return None

def translateAsyncDelayed(text, message_id, player_name=None):
    """Async translation for standard chat using Microsoft API"""
    try:
        # Re-check rate limit before API call
        allowed, error_msg = checkRateLimit(player_name)
        if not allowed:
            logDebug('Rate limit hit for async translation')
            BigWorld.callback(0.1, lambda: displayMessage(message_id, text))
            return
        
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
                        cache_timestamps[text] = time.time()
                    BigWorld.callback(0.1, lambda: displayMessage(message_id, text))
                    return
                
                # Don't translate if English with high confidence
                if detected_lang == 'EN' and confidence > 0.85:
                    logDebug('Detected as English by API, displaying original')
                    with cache_lock:
                        translation_cache[text] = None
                        cache_timestamps[text] = time.time()
                    BigWorld.callback(0.1, lambda: displayMessage(message_id, text))
                    return
                
                # Format and cache
                formatted = '[%s→en] %s | %s' % (detected_lang, translated_text, text)
                
                with cache_lock:
                    translation_cache[text] = formatted
                    cache_timestamps[text] = time.time()
                    
                    # Clean old cache entries if too many
                    if len(translation_cache) > 200:
                        cleanExpiredCache()
                
                # Record successful translation
                recordTranslation(player_name)
                
                BigWorld.callback(0.1, lambda: displayMessage(message_id, formatted))
        
    except urllib2.HTTPError as e:
        error_body = e.read() if hasattr(e, 'read') else ''
        print('[MSTranslator] Async HTTP error %s: %s. Body: %s' % (e.code, str(e), error_body[:200]))
        logDebug('Async HTTP error: %s' % error_body)
        with cache_lock:
            translation_cache[text] = None
            cache_timestamps[text] = time.time()
        BigWorld.callback(0.1, lambda: displayMessage(message_id, text))
        
    except Exception as e:
        print('[MSTranslator] Async translation error: %s' % str(e))
        with cache_lock:
            translation_cache[text] = None
            cache_timestamps[text] = time.time()
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
print('[MSTranslator] Microsoft translator with rate limiting loaded!')