from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app.models.models import User, Conversation, ConversationParticipant, Message as MsgModel
from app.extensions import db

messages = Blueprint('messages', __name__)

@messages.route('/inbox')
@login_required
def inbox():
    conversations = current_user.get_conversations()
    return render_template(
        'messages.html',
        conversations=conversations,
        unread_count=current_user.get_unread_message_count(),
        ConversationParticipant=ConversationParticipant  
    )

@messages.route('/conversation/<int:conversation_id>', methods=['GET'])
@login_required
def view_conversation(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if not conversation.is_participant(current_user.id):
        abort(403)
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation_id, user_id=current_user.id).first()
    if participant:
        participant.mark_as_read()
    other_participants = User.query.join(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        User.id != current_user.id
    ).all()
    messages_list = MsgModel.query.filter_by(conversation_id=conversation_id).order_by(MsgModel.created_at).all()
    return render_template('conversation.html',
                          conversation=conversation,
                          messages=messages_list,
                          other_participants=other_participants)

@messages.route('/conversation/<int:conversation_id>/send', methods=['POST'])
@login_required
def send_message(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if not conversation.is_participant(current_user.id):
        abort(403)
    content = request.form.get('content')
    if not content or content.strip() == '':
        flash("Message cannot be empty", "error")
        return redirect(url_for('messages.view_conversation', conversation_id=conversation_id))
    message = MsgModel(
        conversation_id=conversation_id,
        user_id=current_user.id,
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
        return redirect(url_for('messages.view_conversation', conversation_id=conversation_id))

@messages.route('/new-conversation', methods=['GET'])
@login_required
def new_conversation_form():
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('new_conversation.html', users=users) 

@messages.route('/new-conversation', methods=['POST'])
@login_required
def create_conversation():
    recipient_id = request.form.get('recipient_id')
    initial_message = request.form.get('message')
    if not recipient_id or not initial_message or initial_message.strip() == '':
        flash("Please select a recipient and enter a message", "error")
        return redirect(url_for('messages.new_conversation_form'))
    recipient = User.query.get_or_404(recipient_id)
    existing_conversations = Conversation.query.join(
        ConversationParticipant, Conversation.id == ConversationParticipant.conversation_id
    ).filter(
        ConversationParticipant.user_id == current_user.id
    ).all()
    for conv in existing_conversations:
        participants = [p.user_id for p in conv.participants]
        if len(participants) == 2 and int(recipient_id) in participants:
            flash("Continuing existing conversation", "info")
            message = MsgModel(
                conversation_id=conv.id,
                user_id=current_user.id,
                content=initial_message
            )
            conv.updated_at = datetime.utcnow()
            db.session.add(message)
            db.session.commit()
            return redirect(url_for('messages.view_conversation', conversation_id=conv.id))
    conversation = Conversation()
    db.session.add(conversation)
    db.session.flush()
    conversation.add_participant(current_user.id)
    conversation.add_participant(recipient_id)
    message = MsgModel(
        conversation_id=conversation.id,
        user_id=current_user.id,
        content=initial_message
    )
    db.session.add(message)
    db.session.commit()
    return redirect(url_for('messages.view_conversation', conversation_id=conversation.id))

@messages.route('/conversation/<int:conversation_id>/mark-read', methods=['POST'])
@login_required
def mark_conversation_read(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if not conversation.is_participant(current_user.id):
        abort(403)
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation_id, user_id=current_user.id).first()
    if participant:
        participant.mark_as_read()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Participant record not found'}), 404

@messages.route('/api/conversations')
@login_required
def api_conversations():
    conversations = []
    for conv in current_user.get_conversations():
        other_participants = User.query.join(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conv.id,
            User.id != current_user.id
        ).all()
        last_message = conv.last_message
        participant = ConversationParticipant.query.filter_by(
            conversation_id=conv.id, user_id=current_user.id).first()
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
    return jsonify(conversations)

@messages.route('/api/conversation/<int:conversation_id>/messages')
@login_required
def api_conversation_messages(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if not conversation.is_participant(current_user.id):
        abort(403)
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation_id, user_id=current_user.id).first()
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
            'is_mine': msg.user_id == current_user.id
        })
    return jsonify(messages_data)