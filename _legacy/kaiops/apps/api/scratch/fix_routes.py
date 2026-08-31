import re

with open('app/chat/routes.py', 'r') as f:
    content = f.read()

# Remove the import of chat_db
content = re.sub(r'from \.database_firestore import chat_db\n', '', content)

# In each function, make sure we import get_session_service if we use it
# Wait, I'll just do a global replace for the chat_db calls!
# I already added `from app.chat.agent_service import get_session_service` in many places,
# but it's easier to just put it globally if possible. Oh wait, it might cause circular imports.
# It's better to just replace `chat_db.` with `get_session_service().` everywhere!

content = content.replace('chat_db.get_session(', 'get_session_service().get_api_session(')
content = content.replace('chat_db.delete_session(', 'get_session_service().delete_api_session(')
content = content.replace('chat_db.', 'get_session_service().')

with open('app/chat/routes.py', 'w') as f:
    f.write(content)

print("Fixed routes.py")

