# backend/scoring_service.py
import json
import os
from datetime import datetime
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self, interview_id: str):
        self.interview_id = interview_id
        self.session_dir = f"interview_sessions/{interview_id}"
        os.makedirs(self.session_dir, exist_ok=True)

        self.scores_file = f"{self.session_dir}/scores.json"
        self.initialize_scoring()

    def initialize_scoring(self):
        """Initialize scoring data structure"""
        self.scoring_data = {
            "interview_id": self.interview_id,
            "start_time": datetime.now().isoformat(),
            "questions": [],
            "scores": {"technical": [], "level": [], "overall": []},
            "level_progression": [],
            "proctoring_penalties": [],
            "final_evaluation": None,
        }
        self.save_scores()

    def add_question_score(
        self,
        question: str,
        answer: str,
        technical_score: int,
        level: str,
        analysis: str = "",
    ) -> Dict:
        """Add score for a question"""
        question_data = {
            "question_number": len(self.scoring_data["questions"]) + 1,
            "question": question,
            "answer": answer,
            "technical_score": technical_score,
            "level": level,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat(),
        }

        self.scoring_data["questions"].append(question_data)
        self.scoring_data["scores"]["technical"].append(technical_score)
        self.scoring_data["level_progression"].append(level)

        # Calculate current average
        current_avg = self.calculate_current_average()
        self.scoring_data["scores"]["overall"].append(current_avg)

        self.save_scores()

        return question_data

    def calculate_current_average(self) -> float:
        """Calculate current average score"""
        if not self.scoring_data["scores"]["technical"]:
            return 0.0

        return sum(self.scoring_data["scores"]["technical"]) / len(
            self.scoring_data["scores"]["technical"]
        )

    def calculate_final_evaluation(
        self, final_level: str, proctoring_stats: dict = None
    ) -> Dict:
        """Calculate final evaluation scores with proctoring penalties"""
        if not self.scoring_data["questions"]:
            return {
                "overall_score": 0,
                "technical_avg": 0,
                "final_level": final_level,
                "total_questions": 0,
                "penalty_details": {},
            }

        # Level-based scoring
        level_weights = {"easy": 0.3, "medium": 0.6, "hard": 1.0}
        level_weight = level_weights.get(final_level, 0.3)

        # Technical average
        technical_avg = self.calculate_current_average()

        # Base overall score (70% technical + 30% level)
        base_score = (technical_avg * 0.7) + (level_weight * 100 * 0.3)

        # Apply proctoring penalties if provided
        final_score = base_score
        penalty_details = {
            "base_score": round(base_score, 1),
            "penalties_applied": [],
            "total_penalty": 0,
        }

        if proctoring_stats:
            # Calculate proctoring penalty
            proctoring_penalty = self.calculate_proctoring_penalty(proctoring_stats)
            final_score = max(0, base_score - proctoring_penalty)  # Ensure not negative

            penalty_details.update(
                {
                    "proctoring_penalty": round(proctoring_penalty, 1),
                    "final_score_after_penalties": round(final_score, 1),
                    "proctoring_stats": proctoring_stats,
                }
            )

            # Store penalty details
            self.scoring_data["proctoring_penalties"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "proctoring_stats": proctoring_stats,
                    "penalty_applied": proctoring_penalty,
                }
            )

        # Detailed breakdown
        final_eval = {
            "overall_score": round(final_score, 1),
            "technical_avg": round(technical_avg, 1),
            "final_level": final_level,
            "total_questions": len(self.scoring_data["questions"]),
            "level_progression": self.scoring_data["level_progression"],
            "penalty_details": penalty_details,
            "question_breakdown": [
                {
                    "question": q["question_number"],
                    "score": q["technical_score"],
                    "level": q["level"],
                }
                for q in self.scoring_data["questions"]
            ],
            "strengths": self.identify_strengths(),
            "areas_for_improvement": self.identify_weaknesses(),
            "completion_time": datetime.now().isoformat(),
        }

        self.scoring_data["final_evaluation"] = final_eval
        self.save_scores()

        return final_eval

    def calculate_proctoring_penalty(self, proctoring_data: dict) -> float:
        """Calculate penalty based on proctoring violations"""
        penalty = 0
        penalties_applied = []

        # Tab switching penalty (2 points per switch, max 20 points)
        tab_switches = proctoring_data.get("tab_switch_count", 0)
        if tab_switches > 0:
            tab_penalty = min(tab_switches * 2, 20)  # Max 20 points penalty
            penalty += tab_penalty
            penalties_applied.append(
                f"Tab switches: {tab_switches} (-{tab_penalty} points)"
            )

        # Face detection violations
        face_penalty = 0

        # Multiple people detected (severe violation)
        multiple_faces = proctoring_data.get("multiple_faces", 0)
        if multiple_faces > 0:
            multiple_penalty = 15 * multiple_faces  # 15 points per occurrence
            face_penalty += multiple_penalty
            penalties_applied.append(
                f"Multiple people detected: {multiple_faces} times (-{multiple_penalty} points)"
            )

        # Face covered (moderate violation)
        face_coverings = proctoring_data.get("face_coverings", 0)
        if face_coverings > 0:
            face_cover_penalty = min(face_coverings * 5, 25)  # Max 25 points
            face_penalty += face_cover_penalty
            penalties_applied.append(
                f"Face covered: {face_coverings} times (-{face_cover_penalty} points)"
            )

        # Eyes covered (moderate violation)
        eye_coverings = proctoring_data.get("eye_coverings", 0)
        if eye_coverings > 0:
            eye_cover_penalty = min(eye_coverings * 5, 25)  # Max 25 points
            face_penalty += eye_cover_penalty
            penalties_applied.append(
                f"Eyes covered: {eye_coverings} times (-{eye_cover_penalty} points)"
            )

        # No face detected (minor violation, but frequent)
        no_face_count = proctoring_data.get("no_face_count", 0)
        if no_face_count > 0:
            no_face_penalty = min(no_face_count * 2, 15)  # Max 15 points
            face_penalty += no_face_penalty
            penalties_applied.append(
                f"No face detected: {no_face_count} times (-{no_face_penalty} points)"
            )

        penalty += min(face_penalty, 50)  # Cap face penalties at 50 points

        # Total alerts penalty
        total_alerts = proctoring_data.get("total_alerts", 0)
        if total_alerts > 0:
            alert_penalty = min(
                total_alerts * 1, 10
            )  # Additional penalty for frequent alerts
            penalty += alert_penalty
            penalties_applied.append(
                f"Total alerts: {total_alerts} (-{alert_penalty} points)"
            )

        # Store applied penalties
        proctoring_data["penalty_details"] = {
            "penalties_applied": penalties_applied,
            "total_penalty": min(penalty, 70),
        }

        # Cap total penalty at 70% of base score
        return min(penalty, 70)

    def identify_strengths(self) -> List[str]:
        """Identify candidate strengths based on scores"""
        strengths = []

        # Analyze high-scoring questions
        high_scores = [
            q
            for q in self.scoring_data["questions"]
            if q.get("technical_score", 0) >= 80
        ]

        if len(high_scores) >= 3:
            strengths.append("Strong technical knowledge in core areas")

        # Check level progression
        if "hard" in self.scoring_data["level_progression"]:
            strengths.append("Capable of handling advanced concepts")

        # Check consistency
        scores = self.scoring_data["scores"]["technical"]
        if len(scores) >= 3 and max(scores) - min(scores) <= 20:
            strengths.append("Consistent performance across questions")

        return strengths or ["Demonstrates basic understanding"]

    def identify_weaknesses(self) -> List[str]:
        """Identify areas for improvement"""
        weaknesses = []

        # Analyze low-scoring questions
        low_scores = [
            q
            for q in self.scoring_data["questions"]
            if q.get("technical_score", 0) < 60
        ]

        if low_scores:
            weaknesses.append("Needs improvement in technical depth")

        # Check if stuck in lower levels
        if len(self.scoring_data["level_progression"]) >= 2:
            last_two = self.scoring_data["level_progression"][-2:]
            if last_two == ["easy", "easy"]:
                weaknesses.append("Could benefit from practicing intermediate concepts")

        return weaknesses or ["Continue building experience"]

    def save_scores(self):
        """Save scores to file"""
        try:
            with open(self.scores_file, "w", encoding="utf-8") as f:
                json.dump(self.scoring_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Scores saved to {self.scores_file}")
        except Exception as e:
            logger.error(f"Error saving scores: {e}")

    def get_scores_summary(self) -> Dict:
        """Get summary of scores"""
        return {
            "total_questions": len(self.scoring_data["questions"]),
            "average_score": self.calculate_current_average(),
            "current_level": self.scoring_data["level_progression"][-1]
            if self.scoring_data["level_progression"]
            else "easy",
            "level_history": self.scoring_data["level_progression"],
            "recent_scores": self.scoring_data["scores"]["technical"][-5:]
            if len(self.scoring_data["scores"]["technical"]) > 5
            else self.scoring_data["scores"]["technical"],
        }
