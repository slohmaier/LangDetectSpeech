import addonHandler
import config
import core
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
	'fallback': 'string(default=\'en\')',
}


def getLanguageDisplayName(langCode):
	"""Get translated language name for display, with fallback to code."""
	try:
		desc = languageHandler.getLanguageDescription(langCode)
		if desc:
			return desc
	except Exception:
		pass
	return langCode

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
	"""Get fallback language code."""
	fallback = config.conf['LangDetectSpeech']['fallback'].strip().lower()
	return fallback if fallback else 'en'


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
			fallback = get_fallback()
			synthLangs[fallback] = fallback

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
			fallback_lang = get_fallback()
			if fallback_lang in synthLangs:
				predictedLang = fallback_lang

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

	# Collect all text for language detection
	text = ''
	for item in speechSequence:
		if isinstance(item, str):
			text += item

	if not text.strip():
		return speechSequence

	detectedLang = detectLanguage(text)

	# Build new sequence: prepend detected language, strip existing LangChangeCommands
	newSequence = [LangChangeCommand(detectedLang)]
	for item in speechSequence:
		if not isinstance(item, LangChangeCommand):
			newSequence.append(item)

	log.debug('LangDetectSpeech: Injected LangChangeCommand({0})'.format(detectedLang))
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

		# Warn if automatic language switching is disabled (after NVDA fully starts)
		core.postNvdaStartup.register(self._checkAutoLangSwitching)

	def _checkAutoLangSwitching(self):
		core.postNvdaStartup.unregister(self._checkAutoLangSwitching)
		if not config.conf["speech"]["autoLanguageSwitching"]:
			wx.CallAfter(self._warnAutoLangSwitching)

	def _warnAutoLangSwitching(self):
		# Translators: Warning shown when automatic language switching is disabled in NVDA speech settings.
		if gui.messageBox(
			_('LangDetectSpeech requires "Automatic language switching" to be enabled '
				'in NVDA speech settings.\n\n'
				'Do you want to enable it now?'),
			'LangDetectSpeech',
			wx.YES_NO | wx.ICON_WARNING
		) == wx.YES:
			config.conf["speech"]["autoLanguageSwitching"] = True

	def terminate(self):
		# Unregister the speech sequence filter
		filter_speechSequence.unregister(speechSequenceFilter)
		log.debug('LangDetectSpeech: Unregistered speech sequence filter')

		# Remove settings panel
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(LangDetectSpeechSettings)


class LangDetectSpeechSettings(SettingsPanel):
	# Title of the settings panel (addon name, not translated)
	title = 'LangDetectSpeech'

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Ensure synth languages are up to date
		updateSynthLangs()

		# Build list of languages with display names: [(code, displayName), ...]
		self._languages = []
		for langCode in sorted(synthLangs.keys()):
			displayName = getLanguageDisplayName(langCode)
			self._languages.append((langCode, displayName))

		synthName = speech.synthDriverHandler.getSynth().name
		# Translators: Label for the languages section. {0} is the synthesizer name.
		languagesLabel = _('Languages to detect\n'
			'The synthesizer "{0}" supports the following languages. '
			'Select all that should be considered for automatic detection:').format(synthName)
		langGroupSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=languagesLabel)
		langGroupBox = langGroupSizer.GetStaticBox()
		langGroupHelper = sHelper.addItem(gui.guiHelper.BoxSizerHelper(self, sizer=langGroupSizer))

		# Create individual checkboxes for each language (more accessible than CheckListBox)
		self._langCheckboxes = {}
		for langCode, displayName in self._languages:
			checkbox = wx.CheckBox(langGroupBox, label=displayName)
			langGroupHelper.addItem(checkbox)
			self._langCheckboxes[langCode] = checkbox

		# Translators: Label for fallback language selection.
		# The description is included in the label so screen readers announce it.
		fallbackLabel = _('Fallback language\n'
			'Used when the detected language is not in the list above:')
		self._fallbackChoice = sHelper.addLabeledControl(
			fallbackLabel,
			wx.Choice,
			choices=[lang[1] for lang in self._languages]
		)

		self._loadSettings()

	def _loadSettings(self):
		# Load whitelist and check appropriate checkboxes
		whitelist = get_whitelist()
		for langCode, checkbox in self._langCheckboxes.items():
			checkbox.SetValue(langCode in whitelist)

		# Load fallback language
		fallback = get_fallback()
		for i, (langCode, _) in enumerate(self._languages):
			if langCode == fallback:
				self._fallbackChoice.SetSelection(i)
				break
		else:
			# Default to first item if not found
			if self._languages:
				self._fallbackChoice.SetSelection(0)

	def onSave(self):
		# Save whitelist from checked checkboxes
		newWhitelist = []
		for langCode, checkbox in self._langCheckboxes.items():
			if checkbox.IsChecked():
				newWhitelist.append(langCode)
		config.conf['LangDetectSpeech']['whitelist'] = ', '.join(newWhitelist)

		# Save fallback language
		selection = self._fallbackChoice.GetSelection()
		if selection >= 0 and selection < len(self._languages):
			config.conf['LangDetectSpeech']['fallback'] = self._languages[selection][0]

		log.debug('LangDetectSpeech: Updated settings - whitelist: {0}, fallback: {1}'.format(
			newWhitelist, config.conf['LangDetectSpeech']['fallback']))

	def onPanelActivated(self):
		self._loadSettings()
		self.Show()
