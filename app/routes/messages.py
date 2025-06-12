from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
from app.models.models import User, Conversation, ConversationParticipant, Message as MsgModel
from app.extensions import db

# Configure logging
logger = logging.getLogger(__name__)

messages = Blueprint('messages', __name__)

@login_required(login_url='/login/')
@messages.route('/inbox')
def inbox(request):
    logger.info(f"User {request.user.id} accessed inbox")
    conversations = request.user.get_conversations()
    return render(
        request,
        'messages.html',
        {
            'conversations': conversations,
            'unread_count': request.user.get_unread_message_count(),
            'ConversationParticipant': ConversationParticipant
        }
    )

@login_required(login_url='/login/')
@messages.route('/conversation/<int:conversation_id>', methods=['GET'])
def view_conversation(request, conversation_id):
    logger.info(f"User {request.user.id} viewing conversation {conversation_id}")
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if not conversation.is_participant(request.user.id):
        logger.warning(f"Unauthorized access attempt to conversation {conversation_id} by user {request.user.id}")
        return HttpResponseForbidden()
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation_id, user_id=request.user.id).first()
    if participant:
        participant.mark_as_read()
    other_participants = User.query.join(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        User.id != request.user.id
    ).all()
    messages_list = MsgModel.query.filter_by(conversation_id=conversation_id).order_by(MsgModel.created_at).all()
    return render(request, 'conversation.html',
                          {
                              'conversation': conversation,
                              'messages': messages_list,
                              'other_participants': other_participants
                          })

@login_required(login_url='/login/')
@messages.route('/conversation/<int:conversation_id>/send', methods=['POST'])
def send_message(request, conversation_id):
    logger.info(f"User {request.user.id} attempting to send message in conversation {conversation_id}")
    conversation = Conversation.query.get_or_404(conversation_id)
    if not conversation.is_participant(request.user.id):
        return HttpResponseForbidden()
    content = request.form.get('content')
    if not content or content.strip() == '':
        logger.warning(f"User {request.user.id} attempted to send empty message")
        messages.error(request, "Message cannot be empty")
        return redirect(reverse('messages:view_conversation', args=[conversation_id]))
    message = MsgModel(
        conversation_id=conversation_id,
        user_id=request.user.id,
        content=content
    )
    conversation.updated_at = datetime.utcnow()
    db.session.add(message)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'status': 'success',
            'message': {
                'id': message.id,
                'content': message.content,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'user_id': message.user_id,
                'username': message.user.username
            }
        })
    else:
        return redirect(reverse('messages:view_conversation', args=[conversation_id]))

@login_required(login_url='/login/')
@messages.route('/new-conversation', methods=['GET'])
def new_conversation_form(request):
    logger.info(f"User {request.user.id} accessing new conversation form")
    users = User.query.filter(User.id != request.user.id).limit(20).all()  # Show first 20 by default
    return render(request, 'new_conversation.html', {'users': users})

@login_required(login_url='/login/')
@messages.route('/new-conversation', methods=['POST'])
def create_conversation(request):
    recipient_id = request.form.get('recipient_id')
    initial_message = request.form.get('message')
    if not recipient_id or not initial_message or initial_message.strip() == '':
        messages.error(request, "Please select a recipient and enter a message")
        return redirect(reverse('messages:new_conversation_form'))
    recipient = User.query.get_or_404(recipient_id)
    existing_conversations = Conversation.query.join(
        ConversationParticipant, Conversation.id == ConversationParticipant.conversation_id
    ).filter(
        ConversationParticipant.user_id == request.user.id
    ).all()
    for conv in existing_conversations:
        participants = [p.user_id for p in conv.participants]
        if len(participants) == 2 and int(recipient_id) in participants:
            messages.info(request, "Continuing existing conversation")
            message = MsgModel(
                conversation_id=conv.id,
                user_id=request.user.id,
                content=initial_message
            )
            conv.updated_at = datetime.utcnow()
            db.session.add(message)
            db.session.commit()
            return redirect(reverse('messages:view_conversation', args=[conv.id]))
    conversation = Conversation()
    db.session.add(conversation)
    db.session.flush()
    conversation.add_participant(request.user.id)
    conversation.add_participant(recipient_id)
    message = MsgModel(
        conversation_id=conversation.id,
        user_id=request.user.id,
        content=initial_message
    )
    db.session.add(message)
    db.session.commit()
    return redirect(reverse('messages:view_conversation', args=[conversation.id]))

@login_required(login_url='/login/')
@messages.route('/search-users')
def search_users(request):
    q = request.args.get('q', '').strip()
    if not q:
        return JsonResponse([])
    users = User.query.filter(
        User.id != request.user.id,
        User.username.ilike(f'%{q}%')
    ).limit(20).all()
    return JsonResponse([
        {'id': user.id, 'username': user.username}
        for user in users
    ])

@login_required(login_url='/login/')
@messages.route('/conversation/<int:conversation_id>/mark-read', methods=['POST'])
def mark_conversation_read(request, conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if not conversation.is_participant(request.user.id):
        return HttpResponseForbidden()
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation_id, user_id=request.user.id).first()
    if participant:
        participant.mark_as_read()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Participant record not found'}, status=404)

@messages.route('/api/conversations')
@login_required(login_url='/login/')
def api_conversations(request):
    conversations = []
    for conv in request.user.get_conversations():
        other_participants = User.query.join(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conv.id,
            User.id != request.user.id
        ).all()
        last_message = conv.last_message
        participant = ConversationParticipant.query.filter_by(
            conversation_id=conv.id, user_id=request.user.id).first()
        conversations.append({
            'id': conv.id,
            'participants': [{'id': p.id, 'username': p.username, 'profile_picture': p.profile_picture} for p in other_participants],
            'last_message': {
                'content': last_message.content if last_message else '',
                'created_at': last_message.created_at.strftime('%Y-%m-%d %H:%M:%S') if last_message else '',
                'sender': last_message.user.username if last_message else ''
            },
            'unread': participant.has_unread() if participant else False,
            'updated_at': conv.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return JsonResponse(conversations, safe=False)

@messages.route('/api/conversation/<int:conversation_id>/messages')
@login_required(login_url='/login/')
def api_conversation_messages(request, conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if not conversation.is_participant(request.user.id):
        return HttpResponseForbidden()
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation_id, user_id=request.user.id).first()
    if participant:
        participant.mark_as_read()
    messages_data = []
    for msg in MsgModel.query.filter_by(conversation_id=conversation_id).order_by(MsgModel.created_at).all():
        messages_data.append({
            'id': msg.id,
            'content': msg.content,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'user': {
                'id': msg.user.id,
                'username': msg.user.username,
                'profile_picture': msg.user.profile_picture
            },
            'is_mine': msg.user_id == request.user.id
        })
    return JsonResponse(messages_data, safe=False)

class MessagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and request.path.startswith('/messages/'):
            logger.warning(f"Unauthenticated access attempt to {request.path}")
            return JsonResponse({'error': 'Authentication required'}, status=401)
        return self.get_response(request)

# Update error handlers for Django
def handler401(request, exception=None):
    logger.error(f"Unauthorized access attempt: {request.path}")
    return JsonResponse({'error': 'Unauthorized access'}, status=401)

def handler403(request, exception=None):
    logger.error(f"Forbidden access attempt by user {request.user.id if request.user.is_authenticated else 'anonymous'}: {request.path}")
    return JsonResponse({'error': 'Forbidden access'}, status=403)