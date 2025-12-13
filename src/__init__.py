"""
Voice-to-Text System for Linux Mint
A system-wide voice-to-text application with global hotkey support.
"""

__version__ = "1.0.0"
__author__ = "System Administrator"
__description__ = "Universal voice-to-text system for Linux Mint"

from .application import VoiceToTextApp

__all__ = ['VoiceToTextApp']
