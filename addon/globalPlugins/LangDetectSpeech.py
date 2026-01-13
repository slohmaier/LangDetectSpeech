import addonHandler
import config
import globalPluginHandler
import gui
import speech
import languageHandler
import wx
from gui.settingsDialogs import SettingsPanel
from logHandler import log
from speech.commands import LangChangeCommand
from speech.extensions import filter_speechSequence

from .fast_langdetect import LangDetector, LangDetectConfig

# Make _() available
addonHandler.initTranslation()

# Configuration for settings
config.conf.spec["LangDetectSpeech"] = {
	'whitelist': 'string(default=\'\')',
	'fallback': 'string(default=\'en,de\')',
}

# Global variables
synthClass = None
synthLangs = {}
detector = None


def init_detector():
	"""Initialize the fast-langdetect detector with lite model."""
	global detector
	# Use lite model (bundled, offline), no input length limit for speech
	cfg = LangDetectConfig(model="lite", max_input_length=None)
	detector = LangDetector(cfg)
	log.debug('LangDetectSpeech: Initialized fast-langdetect detector')


def get_whitelist():
	whitelist = config.conf['LangDetectSpeech']['whitelist'].strip()
	if whitelist:
		return [i.strip().lower() for i in whitelist.split(',')]
	else:
		return []


def get_fallback():
	fallback = config.conf['LangDetectSpeech']['fallback'].strip()
	if fallback:
		return [i.strip().lower() for i in fallback.split(',')]
	else:
		return ['en']


def updateSynthLangs():
	"""Update the available synthesizer languages."""
	global synthClass
	global synthLangs
	curSynthClass = str(speech.synthDriverHandler.getSynth().__class__)
	if curSynthClass != synthClass:
		synthClass = curSynthClass
		synthLangs = {}
		try:
			for voiceId in speech.synthDriverHandler.getSynth().availableVoices:
				voice = speech.synthDriverHandler.getSynth().availableVoices[voiceId]
				lang = voice.language.split('_')[0].lower()
				if lang not in synthLangs:
					synthLangs[lang] = voice.language
		except NotImplementedError:
			synthLangs = {}
			for lang in get_fallback():
				synthLangs[lang] = lang

		log.info('LANGPREDICT:\nFound voices:\n' +
			'\n'.join(
				['- {0}: {1}'.format(key, synthLangs[key]) for key in synthLangs]
			)
		)

		# Initialize whitelist if not all languages are in Synthesizer
		whitelist = get_whitelist()
		for lang in whitelist:
			if lang not in synthLangs.keys():
				whitelist = []
				break

		# Initialize with all supported languages, if whitelist empty or reset
		if not whitelist:
			config.conf['LangDetectSpeech']['whitelist'] = ', '.join(synthLangs.keys())


def getDefaultLang():
	"""Get the default language from the current synthesizer."""
	synth = speech.synthDriverHandler.getSynth()
	try:
		return synth.availableVoices[synth.voice].language
	except NotImplementedError:
		return languageHandler.getLanguage()


def detectLanguage(text: str):
	"""Detect language of text and return appropriate language code for synth."""
	global detector

	defaultLang = getDefaultLang()

	# Skip empty or very short text
	text = text.strip()
	if len(text) < 3:
		return defaultLang

	# Initialize detector if needed
	if detector is None:
		init_detector()

	try:
		# Detect language using fast-langdetect
		results = detector.detect(text, k=5)  # Get top 5 candidates
		whitelist = get_whitelist()

		predictedLang = None
		for result in results:
			lang = result['lang'].lower()
			# Check if language is in whitelist (if whitelist is set)
			if not whitelist or lang in whitelist:
				# Check if language is supported by synth
				if lang in synthLangs:
					predictedLang = lang
					break

		# Fallback to default if no match
		if predictedLang is None:
			# Try fallback languages
			for fallback_lang in get_fallback():
				if fallback_lang in synthLangs:
					predictedLang = fallback_lang
					break

		if predictedLang is None:
			predictedLang = defaultLang.split('_')[0].lower()

		log.debug('PREDICTED={0} TEXT={1}'.format(str(predictedLang), text))

	except Exception as e:
		log.debug('LangDetectSpeech: Detection error: ' + str(e))
		predictedLang = defaultLang.split('_')[0].lower()

	# Don't use a different dialect due to sorting
	if defaultLang.lower().startswith(predictedLang):
		return defaultLang
	else:
		return synthLangs.get(predictedLang, defaultLang)


def speechSequenceFilter(speechSequence, *args, **kwargs):
	"""Filter function that processes speech sequences and injects language commands."""
	# Update synth languages if synthesizer changed
	updateSynthLangs()

	newSequence = []
	hasLangCommand = False

	# Check if sequence already has a LangChangeCommand
	for item in speechSequence:
		if isinstance(item, LangChangeCommand) and item.lang:
			hasLangCommand = True
			break

	# Collect all text for language detection
	text = ''
	for item in speechSequence:
		if isinstance(item, str):
			text += item

	# If no existing language command and we have text, detect and prepend
	if not hasLangCommand and text.strip():
		detectedLang = detectLanguage(text)
		newSequence.append(LangChangeCommand(detectedLang))
		log.debug('LangDetectSpeech: Injected LangChangeCommand({0})'.format(detectedLang))

	# Add original sequence
	newSequence.extend(speechSequence)

	log.debug('LangDetectSpeech: ' + str(newSequence))
	return newSequence


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()

		# Add settings to NVDA
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(LangDetectSpeechSettings)

		# Register the speech sequence filter
		filter_speechSequence.register(speechSequenceFilter)
		log.debug('LangDetectSpeech: Registered speech sequence filter')

	def terminate(self):
		# Unregister the speech sequence filter
		filter_speechSequence.unregister(speechSequenceFilter)
		log.debug('LangDetectSpeech: Unregistered speech sequence filter')

		# Remove settings panel
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(LangDetectSpeechSettings)


class LangDetectSpeechSettings(SettingsPanel):
	title = 'LangDetectSpeech'

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Make a title for the Settings-Pane
		synthName = speech.synthDriverHandler.getSynth().name
		description = _('Available languages for Synthesizer "{0}":').format(synthName)
		sHelper.addItem(wx.StaticText(self, label=description))

		# Ensure synth languages are up to date
		updateSynthLangs()

		# Create a checkbox for each language supported by the synth
		self._langCheckboxes = []
		for lang in synthLangs.keys():
			checkbox = wx.CheckBox(self, label=lang)
			sHelper.addItem(checkbox)
			self._langCheckboxes.append(checkbox)

		# Add separator
		sHelper.addItem(wx.StaticLine(self, style=wx.LI_HORIZONTAL))

		# Add label for Fallback languages with a text field
		sHelper.addItem(wx.StaticText(self, label=_('Fallback languages:')))
		self._fallback = wx.TextCtrl(self)
		sHelper.addItem(self._fallback)

		self._loadSettings()

	def _loadSettings(self):
		self._fallback.SetValue(config.conf['LangDetectSpeech']['fallback'])

		# Check the checkbox for a language if in whitelist
		whitelist = get_whitelist()
		for checkbox in self._langCheckboxes:
			checkbox.SetValue(checkbox.GetLabel().lower() in whitelist)

	def onSave(self):
		# Save fallback
		config.conf['LangDetectSpeech']['fallback'] = self._fallback.GetValue()

		# Create list with checked languages
		newWhitelist = []
		for checkbox in self._langCheckboxes:
			if checkbox.GetValue():
				newWhitelist.append(checkbox.GetLabel().lower())

		# Store new checked languages
		config.conf['LangDetectSpeech']['whitelist'] = ', '.join(newWhitelist)
		log.debug('LangDetectSpeech: Updated whitelist to: ' + str(newWhitelist))

	def onPanelActivated(self):
		self._loadSettings()
		self.Show()
