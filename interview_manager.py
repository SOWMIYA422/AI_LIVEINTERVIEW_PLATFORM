# backend/interview_manager.py - FIXED VERSION WITH PROCOTRING PENALTIES
import json
import time
from datetime import datetime
import os
import logging
from typing import Dict, List, Tuple, Optional

from llm_runner import LLMRunner
from config import JOB_ROLE_PROMPTS, INTERVIEW_CONFIG

logger = logging.getLogger(__name__)


class InterviewManager:
    def __init__(self, job_role: str, candidate_name: str = ""):
        self.job_role = job_role
        self.candidate_name = candidate_name
        self.llm = LLMRunner()
        self.interview_id = f"{job_role.replace(' ', '_')}_{int(time.time())}"

        # Get job-specific prompts
        job_key = job_role.lower().replace(" ", "_")
        self.prompts = JOB_ROLE_PROMPTS.get(job_key, JOB_ROLE_PROMPTS["default"])

        # Level tracking
        self.current_level = "easy"
        self.level_questions_asked = 0
        self.consecutive_correct = 0
        self.consecutive_incorrect = 0
        self.level_progression = ["easy"]

        # Interview context
        self.conversation_context = []
        self.last_answer = ""
        self.last_question = ""

        # Session data
        self.session_data = {
            "job_role": job_role,
            "candidate_name": candidate_name,
            "start_time": datetime.now().isoformat(),
            "questions_asked": [],
            "candidate_answers": [],
            "current_question_index": 0,
            "status": "in_progress",
            "evaluation_notes": [],
            "answer_analysis": [],
            "conversation_history": [],
            "current_level": "easy",
            "level_progression": ["easy"],
            "level_scores": {"easy": 0, "medium": 0, "hard": 0},
            "technical_scores": [],
            "final_evaluation": {},
            "consecutive_correct": 0,
            "consecutive_incorrect": 0,
            "proctoring_stats": {},  # Added for proctoring
        }

        # Create session directory
        self.session_dir = f"interview_sessions/{self.interview_id}"
        os.makedirs(self.session_dir, exist_ok=True)

        logger.info(f"Interview started: {job_role}, Candidate: {candidate_name}")

    def get_opening_question(self) -> str:
        """Get the predefined opening question"""
        opening = self.prompts["opening"]
        self.session_data["questions_asked"].append(opening)
        self.session_data["current_question_index"] = 1
        self.last_question = opening

        self.session_data["conversation_history"].append(
            {
                "speaker": "AI Interviewer",
                "text": opening,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Add to conversation context
        self.conversation_context.append(f"Interviewer: {opening}")

        self.save_interview_data()
        return opening

    def evaluate_answer_quality(self, answer: str, question: str) -> int:
        """Evaluate technical quality of answer (0-100) - IMPROVED"""
        evaluation_prompt = f"""
        As an expert interviewer for {self.job_role}, evaluate this answer on a scale of 0-100:
        
        QUESTION: {question}
        ANSWER: {answer}
        
        Scoring guidelines:
        - 90-100: Excellent - Comprehensive, accurate, detailed
        - 80-89: Very Good - Accurate with good detail
        - 70-79: Good - Mostly correct, some gaps
        - 60-69: Satisfactory - Basic understanding
        - 50-59: Below Average - Partial understanding
        - 40-49: Poor - Major gaps
        - 0-39: Very Poor - Incorrect or irrelevant
        
        Focus on: 
        1. Technical accuracy (40%)
        2. Depth of explanation (30%)
        3. Relevance to question (20%)
        4. Clarity and structure (10%)
        
        Return ONLY the number, no text.
        Example: 75
        """

        try:
            response = self.llm.ask(evaluation_prompt)
            # Clean the response
            response = response.strip()

            # Extract number using regex
            import re

            numbers = re.findall(r"\b\d{1,3}\b", response)

            if numbers:
                score = int(numbers[0])
                # Ensure score is within bounds
                score = max(0, min(100, score))

                # Log the evaluation
                if score >= 60:
                    logger.info(f"✅ Answer scored {score} - CORRECT (≥60)")
                else:
                    logger.info(f"❌ Answer scored {score} - INCORRECT (<60)")

                return score
            else:
                logger.warning(f"Could not extract score from LLM response: {response}")
                # Default based on answer length and content
                if len(answer.split()) > 20 and any(
                    keyword in answer.lower()
                    for keyword in [
                        "because",
                        "example",
                        "method",
                        "technique",
                        "approach",
                    ]
                ):
                    return 65  # Likely correct if detailed
                else:
                    return 45  # Likely incorrect if brief

        except Exception as e:
            logger.error(f"Error evaluating answer: {e}")
            # Default based on answer characteristics
            if len(answer) > 50:
                return 55
            else:
                return 40

    def should_promote_level(self) -> bool:
        """Check if candidate should be promoted"""
        if self.current_level == "hard":
            logger.debug(f"❌ Cannot promote: already at HARD level")
            return False

        should_promote = self.consecutive_correct >= 2
        logger.info(
            f"🔍 Promotion check: consecutive_correct={self.consecutive_correct}, need 2 -> {should_promote}"
        )
        return should_promote

    def should_demote_level(self) -> bool:
        """Check if candidate should be demoted"""
        if self.current_level == "easy":
            logger.debug(f"❌ Cannot demote: already at EASY level")
            return False

        should_demote = self.consecutive_incorrect >= 2
        logger.info(
            f"🔍 Demotion check: consecutive_incorrect={self.consecutive_incorrect}, need 2 -> {should_demote}"
        )
        return should_demote

    def determine_next_level(self, technical_score: int) -> str:
        """Determine next level based on performance - FIXED"""
        is_correct = technical_score >= 60
        logger.info(f"🎯 Score: {technical_score}, Is correct: {is_correct}")

        # Store old level for comparison
        old_level = self.current_level

        # Update consecutive counts
        if is_correct:
            self.consecutive_correct += 1
            self.consecutive_incorrect = 0
            logger.info(f"✅ Consecutive correct: {self.consecutive_correct}")
        else:
            self.consecutive_incorrect += 1
            self.consecutive_correct = 0
            logger.info(f"❌ Consecutive incorrect: {self.consecutive_incorrect}")

        self.level_questions_asked += 1
        logger.info(f"📊 Level questions asked: {self.level_questions_asked}")

        # Check promotion/demotion BEFORE changing level
        promotion_needed = False
        demotion_needed = False

        if self.should_promote_level():
            promotion_needed = True
            if self.current_level == "easy":
                new_level = "medium"
            else:  # current_level == "medium"
                new_level = "hard"
            self._change_level(new_level, "promotion")
        elif self.should_demote_level():
            demotion_needed = True
            if self.current_level == "medium":
                new_level = "easy"
            else:  # current_level == "hard"
                new_level = "medium"
            self._change_level(new_level, "demotion")

        # Update session data with current values
        self.session_data["current_level"] = self.current_level
        self.session_data["consecutive_correct"] = self.consecutive_correct
        self.session_data["consecutive_incorrect"] = self.consecutive_incorrect

        # Log level change if any
        if old_level != self.current_level:
            logger.info(
                f"🔄 Level changed: {old_level.upper()} → {self.current_level.upper()}"
            )
            if promotion_needed:
                logger.info(f"🎉 PROMOTED to {self.current_level.upper()} level!")
            elif demotion_needed:
                logger.info(f"⚠️ DEMOTED to {self.current_level.upper()} level!")
        else:
            logger.info(f"⏸️ Level unchanged: {self.current_level.upper()}")

        return self.current_level

    def _change_level(self, new_level: str, reason: str):
        """Change level with logging - FIXED: DO NOT reset consecutive counters"""
        old_level = self.current_level
        self.current_level = new_level
        self.level_progression.append(new_level)

        # Reset only level questions asked
        self.level_questions_asked = 0

        # DO NOT reset consecutive_correct and consecutive_incorrect!
        # They should carry over to the new level

        logger.info(f"🎯 Level {reason}: {old_level.upper()} → {new_level.upper()}")
        logger.info(
            f"📊 Counters after level change: correct={self.consecutive_correct}, incorrect={self.consecutive_incorrect}"
        )

        # Update session data
        self.session_data["current_level"] = new_level
        self.session_data["level_progression"] = self.level_progression

    def analyze_answer_and_generate_question(
        self, question: str, answer: str
    ) -> Tuple[str, str]:
        """Analyze answer and generate next question based on answer and job role"""

        # Update conversation context
        self.conversation_context.append(f"Candidate: {answer}")
        self.last_answer = answer
        self.last_question = question

        # Prepare context for the LLM
        conversation_summary = "\n".join(
            self.conversation_context[-4:]
        )  # Last 4 exchanges

        level_context = self.prompts["level_context"][self.current_level]

        prompt = f"""You are conducting a {self.job_role} interview at {self.current_level} level.

JOB ROLE CONTEXT: {self.prompts.get("context", "Professional interview")}
LEVEL CONTEXT: {level_context}

RECENT CONVERSATION:
{conversation_summary}

INSTRUCTIONS:
1. First, briefly analyze the candidate's answer (2-3 sentences)
   - What did they do well?
   - What could be improved?
   - How relevant is it to {self.job_role}?

2. Then, generate a follow-up {self.current_level.upper()} level question
   - Based on their previous answer
   - Related to {self.job_role} role
   - Progress the interview naturally
   - Challenge them appropriately for their level

FORMAT YOUR RESPONSE EXACTLY AS:
ANALYSIS: [Your analysis here]
QUESTION: [Your next question here]"""

        try:
            response = self.llm.ask(prompt)

            # Parse response
            analysis = ""
            next_question = ""

            if "ANALYSIS:" in response and "QUESTION:" in response:
                parts = response.split("QUESTION:")
                analysis = parts[0].replace("ANALYSIS:", "").strip()
                next_question = parts[1].strip()
            else:
                # Fallback parsing
                lines = [line.strip() for line in response.split("\n") if line.strip()]
                if len(lines) >= 2:
                    analysis = lines[0]
                    next_question = lines[1]
                else:
                    analysis = "Answer received. Continuing interview."
                    next_question = self._generate_fallback_question()

            # Add interviewer's next question to conversation context
            self.conversation_context.append(f"Interviewer: {next_question}")

            return analysis, next_question

        except Exception as e:
            logger.error(f"Error generating question: {e}")
            return "Analysis not available.", self._generate_fallback_question()

    def _generate_fallback_question(self) -> str:
        """Generate a fallback question when LLM fails"""
        fallback_questions = {
            "easy": [
                f"Could you tell me more about your experience with {self.job_role.lower()}?",
                f"What interests you most about being a {self.job_role}?",
                f"Can you describe a basic project related to {self.job_role.lower()} that you've worked on?",
            ],
            "medium": [
                f"How would you approach a typical challenge in {self.job_role.lower()}?",
                f"What are the key skills needed for a {self.job_role} role?",
                f"Can you explain a technical concept relevant to {self.job_role.lower()}?",
            ],
            "hard": [
                f"How would you handle a complex situation in {self.job_role.lower()}?",
                f"What advanced techniques would you use in {self.job_role.lower()}?",
                f"Can you discuss a strategic approach to {self.job_role.lower()} problems?",
            ],
        }

        import random

        questions = fallback_questions.get(
            self.current_level, fallback_questions["easy"]
        )
        return random.choice(questions)

    def process_answer(self, question: str, answer: str) -> Tuple[Dict, str]:
        """Process answer and generate next question based on the answer"""
        logger.info(f"Processing answer for: {question[:50]}...")

        # Evaluate technical quality FIRST
        technical_score = self.evaluate_answer_quality(answer, question)
        self.session_data["technical_scores"].append(technical_score)

        # Determine next level based on performance
        next_level = self.determine_next_level(technical_score)
        logger.info(f"🎯 Next level determined: {next_level}")

        # Analyze and generate next question based on the answer
        analysis, next_question = self.analyze_answer_and_generate_question(
            question, answer
        )

        # Create Q&A record
        qa_record = {
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "next_question": next_question,
            "level": next_level,
            "technical_score": technical_score,
            "level_questions_asked": self.level_questions_asked,
            "consecutive_correct": self.consecutive_correct,
            "consecutive_incorrect": self.consecutive_incorrect,
        }

        # Update session data
        self.session_data["candidate_answers"].append(qa_record)
        self.session_data["answer_analysis"].append(analysis)
        self.session_data["questions_asked"].append(next_question)
        self.session_data["current_question_index"] += 1
        self.session_data["conversation_history"].extend(
            [
                {
                    "speaker": "Candidate",
                    "text": answer,
                    "timestamp": datetime.now().isoformat(),
                },
                {
                    "speaker": "AI Interviewer",
                    "text": next_question,
                    "timestamp": datetime.now().isoformat(),
                },
            ]
        )

        self.save_interview_data()

        return qa_record, next_question

    def get_next_question_without_answer(self, current_question: str) -> str:
        """Generate next question when candidate skips or doesn't provide clear answer"""
        logger.info(
            f"Generating next question without answer for: {current_question[:50]}..."
        )

        # Use the last answer if available, otherwise use context
        last_answer_text = (
            self.last_answer
            if self.last_answer
            else "The candidate did not provide a clear answer."
        )

        # Prepare context
        level_context = self.prompts["level_context"][self.current_level]

        prompt = f"""You are conducting a {self.job_role} interview at {self.current_level} level.

PREVIOUS QUESTION: {current_question}
CANDIDATE'S RESPONSE: {last_answer_text}

INSTRUCTIONS:
Generate a follow-up {self.current_level.upper()} level question for a {self.job_role} interview.
The question should:
1. Be appropriate for {self.current_level} level
2. Be related to {self.job_role}
3. Progress the interview naturally
4. Not require knowledge of the previous answer

IMPORTANT: Return ONLY the question, no analysis, no extra text.
QUESTION:"""

        try:
            response = self.llm.ask(prompt)

            # Clean the response
            next_question = response.strip()
            if "QUESTION:" in next_question:
                next_question = next_question.split("QUESTION:")[-1].strip()

            # Ensure it's a reasonable length
            if len(next_question) < 10 or len(next_question) > 500:
                next_question = self._generate_fallback_question()

            # Update session data
            self.session_data["questions_asked"].append(next_question)
            self.session_data["current_question_index"] += 1
            self.session_data["conversation_history"].append(
                {
                    "speaker": "AI Interviewer",
                    "text": next_question,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Update conversation context
            self.conversation_context.append(f"Candidate: [Skipped or unclear answer]")
            self.conversation_context.append(f"Interviewer: {next_question}")

            self.save_interview_data()

            return next_question

        except Exception as e:
            logger.error(f"Error generating next question without answer: {e}")
            return self._generate_fallback_question()

    def save_interview_data(self):
        """Save interview data to JSON file"""
        try:
            data_file = f"{self.session_dir}/interview_data.json"
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(self.session_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving interview data: {e}")

    def calculate_final_evaluation(self, proctoring_stats: dict = None) -> Dict:
        """Calculate final evaluation scores with proctoring penalties"""
        # Level-based score
        level_weights = {"easy": 30, "medium": 70, "hard": 100}
        level_score = level_weights.get(self.current_level, 30)

        # Technical score
        technical_scores = self.session_data.get("technical_scores", [])
        if technical_scores:
            technical_score = sum(technical_scores) / len(technical_scores)
        else:
            technical_score = 50

        # Base overall score (60% level + 40% technical)
        base_score = (level_score * 0.6) + (technical_score * 0.4)

        # Apply proctoring penalties if provided
        final_score = base_score
        penalty_details = {
            "base_score": round(base_score, 1),
            "penalties_applied": [],
            "total_penalty": 0,
        }

        if proctoring_stats:
            # Calculate proctoring penalty
            proctoring_penalty = self._calculate_proctoring_penalty(proctoring_stats)
            final_score = max(0, base_score - proctoring_penalty)  # Ensure not negative

            penalty_details.update(
                {
                    "proctoring_penalty": round(proctoring_penalty, 1),
                    "final_score_after_penalties": round(final_score, 1),
                    "proctoring_stats": proctoring_stats,
                }
            )

        return {
            "final_level": self.current_level,
            "level_score": level_score,
            "technical_score": round(technical_score, 1),
            "base_score": round(base_score, 1),
            "overall_score": round(final_score, 1),
            "level_progression": self.level_progression,
            "total_questions": len(self.session_data["questions_asked"]),
            "questions_answered": len(self.session_data["candidate_answers"]),
            "completion_time": datetime.now().isoformat(),
            "performance_summary": self._generate_performance_summary(),
            "penalty_details": penalty_details,
        }

    def _calculate_proctoring_penalty(self, proctoring_stats: dict) -> float:
        """Calculate penalty based on proctoring violations"""
        penalty = 0
        penalties_applied = []

        # Tab switching penalty (2 points per switch, max 20 points)
        tab_switches = proctoring_stats.get("tab_switch_count", 0)
        if tab_switches > 0:
            tab_penalty = min(tab_switches * 2, 20)  # Max 20 points penalty
            penalty += tab_penalty
            penalties_applied.append(
                f"Tab switches: {tab_switches} (-{tab_penalty} points)"
            )

        # Face detection violations
        face_penalty = 0

        # Multiple people detected (severe violation)
        multiple_faces = proctoring_stats.get("multiple_faces", 0)
        if multiple_faces > 0:
            multiple_penalty = 15 * multiple_faces  # 15 points per occurrence
            face_penalty += multiple_penalty
            penalties_applied.append(
                f"Multiple people detected: {multiple_faces} times (-{multiple_penalty} points)"
            )

        # Face covered (moderate violation)
        face_coverings = proctoring_stats.get("face_coverings", 0)
        if face_coverings > 0:
            face_cover_penalty = min(face_coverings * 5, 25)  # Max 25 points
            face_penalty += face_cover_penalty
            penalties_applied.append(
                f"Face covered: {face_coverings} times (-{face_cover_penalty} points)"
            )

        # Eyes covered (moderate violation)
        eye_coverings = proctoring_stats.get("eye_coverings", 0)
        if eye_coverings > 0:
            eye_cover_penalty = min(eye_coverings * 5, 25)  # Max 25 points
            face_penalty += eye_cover_penalty
            penalties_applied.append(
                f"Eyes covered: {eye_coverings} times (-{eye_cover_penalty} points)"
            )

        # No face detected (minor violation, but frequent)
        no_face_count = proctoring_stats.get("no_face_count", 0)
        if no_face_count > 0:
            no_face_penalty = min(no_face_count * 2, 15)  # Max 15 points
            face_penalty += no_face_penalty
            penalties_applied.append(
                f"No face detected: {no_face_count} times (-{no_face_penalty} points)"
            )

        penalty += min(face_penalty, 50)  # Cap face penalties at 50 points

        # Total alerts penalty
        total_alerts = proctoring_stats.get("total_alerts", 0)
        if total_alerts > 0:
            alert_penalty = min(
                total_alerts * 1, 10
            )  # Additional penalty for frequent alerts
            penalty += alert_penalty
            penalties_applied.append(
                f"Total alerts: {total_alerts} (-{alert_penalty} points)"
            )

        # Cap total penalty at 70% of base score
        final_penalty = min(penalty, 70)

        # Store penalties in proctoring_stats
        if "penalty_details" in proctoring_stats:
            proctoring_stats["penalty_details"]["penalties_applied"] = penalties_applied
            proctoring_stats["penalty_details"]["total_penalty"] = final_penalty

        return final_penalty

    def _generate_performance_summary(self) -> str:
        """Generate performance summary"""
        if self.current_level == "hard":
            return "Excellent performance - reached the highest level demonstrating advanced knowledge."
        elif self.current_level == "medium":
            return "Good performance - solid understanding of intermediate concepts."
        else:
            return "Basic performance - demonstrated foundational knowledge with room for growth."

    def end_interview(self, proctoring_stats: dict = None) -> str:
        """End interview and return final feedback with proctoring penalties"""
        self.session_data["status"] = "completed"
        self.session_data["end_time"] = datetime.now().isoformat()

        # Store proctoring stats
        if proctoring_stats:
            self.session_data["proctoring_stats"] = proctoring_stats

        # Calculate final evaluation WITH proctoring penalties
        final_evaluation = self.calculate_final_evaluation(proctoring_stats)
        self.session_data["final_evaluation"] = final_evaluation

        self.save_interview_data()

        # Generate feedback with penalty information
        feedback = self._generate_final_feedback(final_evaluation, proctoring_stats)

        logger.info(
            f"Interview ended. Level: {self.current_level}, "
            f"Score: {final_evaluation['overall_score']}%, "
            f"Penalties: {final_evaluation.get('penalty_details', {}).get('total_penalty', 0)}"
        )

        return feedback

    def _generate_final_feedback(
        self, final_evaluation: dict, proctoring_stats: dict = None
    ) -> str:
        """Generate final feedback with proctoring insights"""

        base_feedback = ""
        if self.current_level == "hard":
            base_feedback = f"Excellent! You reached HARD level."
        elif self.current_level == "medium":
            base_feedback = f"Good! You reached MEDIUM level."
        else:
            base_feedback = f"Thank you! You reached EASY level."

        # Add score
        base_feedback += f" Your final score is {final_evaluation['overall_score']}%."

        # Add penalty information if any
        penalty = final_evaluation.get("penalty_details", {}).get("total_penalty", 0)
        if penalty > 0:
            base_score = final_evaluation.get("penalty_details", {}).get(
                "base_score", 0
            )
            base_feedback += (
                f" (Base score: {base_score}%, Penalties: -{penalty} points)"
            )

        # Add proctoring feedback if applicable
        if proctoring_stats:
            proctoring_feedback = []

            # Tab switching feedback
            tab_switches = proctoring_stats.get("tab_switch_count", 0)
            if tab_switches > 0:
                proctoring_feedback.append(f"Tab switches: {tab_switches}")

            # Face detection feedback
            if proctoring_stats.get("multiple_faces", 0) > 0:
                proctoring_feedback.append("Multiple people detected")

            if proctoring_stats.get("face_coverings", 0) > 0:
                proctoring_feedback.append("Face covering detected")

            if proctoring_stats.get("eye_coverings", 0) > 0:
                proctoring_feedback.append("Eye covering detected")

            if proctoring_stats.get("no_face_count", 0) > 5:
                proctoring_feedback.append("Frequent face disappearance")

            if proctoring_feedback:
                base_feedback += f" Proctoring notes: {', '.join(proctoring_feedback)}."

        return base_feedback

    def get_interview_summary(self) -> Dict:
        """Get interview progress summary"""
        return {
            "total_questions": len(self.session_data["questions_asked"]),
            "progress": f"{len(self.session_data['questions_asked'])}/{INTERVIEW_CONFIG['max_questions']}",
            "candidate_name": self.candidate_name,
            "job_role": self.job_role,
            "current_level": self.current_level,
            "level_progression": self.level_progression,
            "consecutive_correct": self.consecutive_correct,
            "consecutive_incorrect": self.consecutive_incorrect,
        }
