from collections import OrderedDict
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response


class StandardResultsSetPagination(LimitOffsetPagination):
    default_limit = 25

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('totalCount', self.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('data', data),
        ]))
