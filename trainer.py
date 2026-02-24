from core import falar



class PronunciationTrainer:
    
    
    def __init__(self, lexicon_manager):
        self.lexicon = lexicon_manager
        self.learning_mode = False
        self.current_word = None
    
    def is_learning(self):
        
        return self.learning_mode
    
    def start_learning(self, word):
        
        self.learning_mode = True
        self.current_word = word.lower().strip()
        
        falar.speak(f"I'm ready to learn the word: '{self.current_word}'.", "learning")
        
        if self.lexicon.word_exists(self.current_word):
            current_phonemes = self.lexicon.get_pronunciation(self.current_word)
            falar.speak(f"This word already exists in my vocabulary.", "learning")
            falar.speak(f"Current pronunciation: {current_phonemes[0] if current_phonemes else 'unknown'}", "learning")
            falar.speak("Say 'update' to change it, 'cancel' to stop, or say the new pronunciation.", "learning")
            return True
        else:
            suggestions = self.lexicon.get_phonetic_suggestions(self.current_word)
            if suggestions:
                falar.speak(f"Suggested pronunciation: {suggestions[0]}", "learning")
                falar.speak("Say 'accept' to use this pronunciation, or say your own pronunciation.", "learning")
            else:
                falar.speak(f"Please say how to pronounce '{self.current_word}'.", "learning")
            return True
    
    def process_learning_response(self, response_text):
        
        if not self.learning_mode or not self.current_word:
            falar.speak("I'm not in learning mode right now.", "error")
            return None
        
        response = response_text.lower().strip()
        
        if response in ["cancel", "stop", "never mind", "forget it"]:
            falar.speak("Learning cancelled.", "learning")
            self.reset_learning()
            return "cancelled"
        
        if response in ["accept", "yes", "use it", "that's correct"]:
            suggestions = self.lexicon.get_phonetic_suggestions(self.current_word)
            if suggestions:
                success = self.lexicon.add_word(
                    self.current_word,
                    [suggestions[0]],
                    learned_from="auto_accept",
                    confidence=0.8
                )
                if success:
                    falar.speak(f"Perfect! I've learned '{self.current_word}' with the suggested pronunciation.", "success")
                    self.reset_learning()
                    return "learned"
        
        if response in ["update", "change", "different"]:
            falar.speak(f"Please say the new pronunciation for '{self.current_word}'.", "learning")
            return "waiting_pronunciation"
        
        phonemes = [response.upper()]
        
        success = self.lexicon.add_word(
            self.current_word,
            phonemes,
            learned_from="user_direct",
            confidence=0.9
        )
        
        if success:
            falar.speak(f"Excellent! I've learned '{self.current_word}' as '{phonemes[0]}'.", "success")
            self.reset_learning()
            return "learned"
        else:
            falar.speak("There was an error saving the word. Please try again.", "error")
            self.reset_learning()
            return "error"
    
    def reset_learning(self):
        
        self.learning_mode = False
        self.current_word = None
