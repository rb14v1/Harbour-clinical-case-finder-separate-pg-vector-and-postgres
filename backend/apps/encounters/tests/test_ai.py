import math

from django.conf import settings
from django.test import TestCase

from apps.common.ai import get_embedding, is_stub_mode


class EmbeddingStubTests(TestCase):
    """No OPENAI_API_KEY is set in the test environment, so get_embedding
    always exercises the deterministic stub path."""

    def test_deterministic_for_same_text(self):
        self.assertEqual(get_embedding("chest pain on exertion"), get_embedding("chest pain on exertion"))

    def test_different_text_gives_different_vector(self):
        self.assertNotEqual(get_embedding("chest pain"), get_embedding("itchy rash"))

    def test_correct_dimensions(self):
        self.assertEqual(len(get_embedding("some clinical text")), settings.EMBEDDING_DIMENSIONS)
        self.assertEqual(settings.EMBEDDING_DIMENSIONS, 1536)

    def test_l2_normalized(self):
        vector = get_embedding("some clinical text")
        norm = math.sqrt(sum(x * x for x in vector))
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_stub_mode_active_without_key(self):
        self.assertTrue(is_stub_mode())
