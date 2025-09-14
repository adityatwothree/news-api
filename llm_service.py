import json
import re
from typing import Dict, List, Optional

import google.generativeai as genai
import openai
from loguru import logger

from config import settings
from models import QueryAnalysis, QueryIntent

# Initialize clients based on provider
openai_client = None
gemini_client = None

if settings.llm_provider == "openai" and settings.openai_api_key:
    openai_client = openai.OpenAI(api_key=settings.openai_api_key)
elif settings.llm_provider == "gemini" and settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)
    gemini_client = genai.GenerativeModel(settings.gemini_model)


class LLMService:
    """Service for LLM operations."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.openai_model = settings.openai_model
        self.gemini_model = settings.gemini_model

    async def analyze_query(
        self, query: str, user_location: Optional[Dict[str, float]] = None
    ) -> QueryAnalysis:
        """Analyze user query to extract entities, concepts, and intent."""
        try:
            if self.provider == "openai" and openai_client:
                return await self._analyze_with_openai(query, user_location)
            elif self.provider == "gemini" and gemini_client:
                return await self._analyze_with_gemini(query, user_location)
            else:
                return self._fallback_query_analysis(query, user_location)

        except Exception as e:
            logger.info(f"Error analyzing query: {e}")
            # Fallback to basic analysis
            return self._fallback_query_analysis(query, user_location)

    async def _analyze_with_openai(
        self, query: str, user_location: Optional[Dict[str, float]] = None
    ) -> QueryAnalysis:
        """Analyze query using OpenAI."""
        prompt = self._build_query_analysis_prompt(query, user_location)

        response = await openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing news queries to extract entities, concepts, and determine user intent.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        result = response.choices[0].message.content
        return self._parse_query_analysis(result, user_location)

    async def _analyze_with_gemini(
        self, query: str, user_location: Optional[Dict[str, float]] = None
    ) -> QueryAnalysis:
        """Analyze query using Gemini."""
        prompt = self._build_query_analysis_prompt(query, user_location)

        response = await gemini_client.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=500,
            ),
        )

        result = response.text
        return self._parse_query_analysis(result, user_location)

    def _build_query_analysis_prompt(
        self, query: str, user_location: Optional[Dict[str, float]] = None
    ) -> str:
        """Build prompt for query analysis."""
        location_context = ""
        if user_location:
            location_context = f"\nUser location: {user_location['latitude']}, {user_location['longitude']}"

        return f"""
Analyze this news query and extract the following information:
Query: "{query}"{location_context}

Please provide a JSON response with:
1. "entities": List of named entities (people, organizations, locations, events)
2. "concepts": List of key concepts and topics
3. "intent": One of: "category", "source", "search", "score", "nearby", "trending"
4. "location": If location is relevant, provide {{"latitude": float, "longitude": float}}
5. "search_query": If this is a search query, provide the cleaned search terms
6. "category": If a specific category is mentioned (e.g., "technology", "sports", "politics")
7. "source": If a specific news source is mentioned (e.g., "CNN", "BBC", "Reuters")
8. "score_threshold": If relevance score is mentioned, provide the threshold

Examples:
- "Latest technology news" → intent: "category", category: "technology"
- "News from CNN" → intent: "source", source: "CNN"
- "Elon Musk Twitter acquisition" → intent: "search", search_query: "Elon Musk Twitter acquisition"
- "High relevance news" → intent: "score", score_threshold: 0.7
- "News near me" → intent: "nearby"
- "What's trending" → intent: "trending"

Response (JSON only):
"""

    def _parse_query_analysis(
        self, result: str, user_location: Optional[Dict[str, float]] = None
    ) -> QueryAnalysis:
        """Parse LLM response into QueryAnalysis object."""
        try:
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

            # Map intent string to enum
            intent_str = data.get("intent", "search").lower()
            intent_mapping = {
                "category": QueryIntent.CATEGORY,
                "source": QueryIntent.SOURCE,
                "search": QueryIntent.SEARCH,
                "score": QueryIntent.SCORE,
                "nearby": QueryIntent.NEARBY,
                "trending": QueryIntent.TRENDING,
            }
            intent = intent_mapping.get(intent_str, QueryIntent.SEARCH)

            return QueryAnalysis(
                entities=data.get("entities", []),
                concepts=data.get("concepts", []),
                intent=intent,
                location=data.get("location")
                or (user_location.dict() if user_location else None),
                search_query=data.get("search_query"),
                category=data.get("category"),
                source=data.get("source"),
                score_threshold=data.get("score_threshold"),
            )

        except Exception as e:
            logger.info(f"Error parsing query analysis: {e}")
            return self._fallback_query_analysis(result, user_location)

    def _fallback_query_analysis(
        self, query: str, user_location: Optional[Dict[str, float]] = None
    ) -> QueryAnalysis:
        """Fallback analysis when LLM fails."""
        query_lower = query.lower()

        # Simple keyword-based intent detection
        if any(
            word in query_lower
            for word in [
                "category",
                "type",
                "sports",
                "technology",
                "politics",
                "business",
            ]
        ):
            intent = QueryIntent.CATEGORY
            self._extract_category(query_lower)
        elif any(
            word in query_lower
            for word in ["from", "source", "cnn", "bbc", "reuters", "times"]
        ):
            intent = QueryIntent.SOURCE
            self._extract_source(query_lower)
        elif any(
            word in query_lower for word in ["near", "nearby", "location", "around"]
        ):
            intent = QueryIntent.NEARBY
        elif any(word in query_lower for word in ["trending", "popular", "viral"]):
            intent = QueryIntent.TRENDING
        elif any(word in query_lower for word in ["score", "relevance", "important"]):
            intent = QueryIntent.SCORE
        else:
            intent = QueryIntent.SEARCH

        return QueryAnalysis(
            entities=self._extract_entities(query),
            concepts=self._extract_concepts(query),
            intent=intent,
            location=user_location,
            search_query=query if intent == QueryIntent.SEARCH else None,
            category=self._extract_category(query_lower)
            if intent == QueryIntent.CATEGORY
            else None,
            source=self._extract_source(query_lower)
            if intent == QueryIntent.SOURCE
            else None,
        )

    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities using simple pattern matching."""
        entities = []
        # Common entity patterns
        patterns = [
            r"\b[A-Z][a-z]+ [A-Z][a-z]+\b",  # Proper names
            r"\b[A-Z]{2,}\b",  # Acronyms
            r"\b(?:Mr|Ms|Dr|Prof)\. [A-Z][a-z]+\b",  # Titles
        ]

        for pattern in patterns:
            matches = re.findall(pattern, query)
            entities.extend(matches)

        return list(set(entities))

    def _extract_concepts(self, query: str) -> List[str]:
        """Extract concepts using keyword matching."""
        concept_keywords = {
            "technology": ["tech", "ai", "software", "computer", "internet", "digital"],
            "politics": [
                "election",
                "government",
                "president",
                "minister",
                "parliament",
            ],
            "sports": ["football", "cricket", "basketball", "tennis", "olympics"],
            "business": ["economy", "market", "stock", "company", "business"],
            "health": ["health", "medical", "disease", "hospital", "doctor"],
            "entertainment": ["movie", "music", "celebrity", "actor", "singer"],
        }

        concepts = []
        query_lower = query.lower()

        for concept, keywords in concept_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                concepts.append(concept)

        return concepts

    def _extract_category(self, query: str) -> Optional[str]:
        """Extract category from query."""
        category_mapping = {
            "technology": "technology",
            "tech": "technology",
            "sports": "sports",
            "politics": "politics",
            "business": "business",
            "health": "health",
            "entertainment": "entertainment",
            "world": "world",
            "national": "national",
        }

        for keyword, category in category_mapping.items():
            if keyword in query:
                return category

        return None

    def _extract_source(self, query: str) -> Optional[str]:
        """Extract news source from query."""
        source_mapping = {
            "cnn": "CNN",
            "bbc": "BBC",
            "reuters": "Reuters",
            "times": "The New York Times",
            "guardian": "The Guardian",
            "fox": "Fox News",
            "nbc": "NBC",
            "abc": "ABC",
        }

        for keyword, source in source_mapping.items():
            if keyword in query:
                return source

        return None

    async def summarize_article(self, title: str, description: str) -> str:
        """Generate a summary for an article using LLM."""
        try:
            if self.provider == "openai" and openai_client:
                return await self._summarize_with_openai(title, description)
            elif self.provider == "gemini" and gemini_client:
                return await self._summarize_with_gemini(title, description)
            else:
                return (
                    description[:200] + "..." if len(description) > 200 else description
                )

        except Exception as e:
            logger.info(f"Error generating summary: {e}")
            # Fallback to truncated description
            return description[:200] + "..." if len(description) > 200 else description

    async def _summarize_with_openai(self, title: str, description: str) -> str:
        """Generate summary using OpenAI."""
        prompt = f"""
Summarize this news article in 2-3 sentences, focusing on the key facts and main points:

Title: {title}
Description: {description}

Summary:
"""

        response = await openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at summarizing news articles concisely and accurately.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=150,
        )

        return response.choices[0].message.content.strip()

    async def _summarize_with_gemini(self, title: str, description: str) -> str:
        """Generate summary using Gemini."""
        prompt = f"""
Summarize this news article in 2-3 sentences, focusing on the key facts and main points:

Title: {title}
Description: {description}

Summary:
"""

        response = await gemini_client.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=150,
            ),
        )

        return response.text.strip()


# Global LLM service instance
llm_service = LLMService()
