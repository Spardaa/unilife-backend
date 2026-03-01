import pytest
from unittest.mock import patch, MagicMock
from app.api.chat import chat
from app.schemas.chat import ChatRequest

@pytest.mark.asyncio
async def test_chat_limit_reached():
    from app.api.chat import MAX_DAILY_AI_REQUESTS
    
    with patch("app.api.chat.db_service") as mock_db:
        # Mock limit reached
        mock_db.check_and_increment_ai_request.return_value = False
        
        with patch("app.api.chat.conversation_service") as mock_conv:
            mock_conv.get_conversation.return_value = None
            
            mock_conversation = MagicMock()
            mock_conversation.id = "test_conv_id"
            mock_conv.create_conversation.return_value = mock_conversation
            
            with patch("app.api.chat.agent_orchestrator") as mock_orchestrator:
                request = ChatRequest(
                    user_id="test_user",
                    message="Hello AI",
                    conversation_id=None
                )
                
                response = await chat(request)
                
                assert response.reply == f"抱歉，您今天已经达到了每日 {MAX_DAILY_AI_REQUESTS} 次对话请求上限。请明天再来吧！"
                assert response.conversation_id == "test_conv_id"
                
                # Verify that orchestrator wasn't called
                mock_orchestrator.process_message.assert_not_called()
