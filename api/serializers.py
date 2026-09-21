from rest_framework import serializers


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)


class WeekTallySerializer(serializers.Serializer):
    completed = serializers.IntegerField()
    total = serializers.IntegerField()
    week_complete = serializers.BooleanField()


class CompletionSerializer(serializers.Serializer):
    completed = serializers.BooleanField()
    week_tally = WeekTallySerializer(required=False)
